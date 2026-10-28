"""The services the migration fixture registers: an upgrading user store."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_dependency_injection import as_service
from xtr_password_hasher import Pbkdf2PasswordHasher
from xtr_security_core import InMemoryUser
from xtr_security_core.exception import UserNotFoundError
from xtr_security_core.user.password_upgrader_interface import PasswordUpgraderInterface
from xtr_security_core.user.user_interface import UserInterface
from xtr_security_core.user.user_provider_interface import UserProviderInterface
from xtr_security_http import UserBadge
from xtr_security_http.access_token.access_token_handler_interface import (
    AccessTokenHandlerInterface,
)
from xtr_security_http.exception import InvalidAccessTokenError

if TYPE_CHECKING:
    from xtr_password_hasher import PasswordAuthenticatedUserInterface

__all__ = ["PLAINTEXT", "STORED_HASH", "MigrationTokenHandler", "UpgradingUserProvider"]

#: The plaintext the fixture user's stored hash was made from.
PLAINTEXT = "s3cret"

#: The stored hash: PBKDF2 under the parameters the fixture's hasher
#: configuration names as a migrate-from source, so the wired migrating
#: hasher verifies it and flags it for a rehash.
STORED_HASH = Pbkdf2PasswordHasher().hash(PLAINTEXT)


@final
@as_service
class UpgradingUserProvider(UserProviderInterface, PasswordUpgraderInterface):
    """Loads the fixture's one user and records every hash it is asked to store."""

    __slots__ = ("stored_hashes",)

    def __init__(self) -> None:
        self.stored_hashes: list[str] = []

    @override
    async def load_user_by_identifier(self, identifier: str) -> UserInterface:
        """Return the fixture user, whose stored hash is a legacy PBKDF2 one.

        Raises:
            UserNotFoundError: For any identifier but the fixture user's.
        """
        if identifier != "alice":
            raise UserNotFoundError(user_identifier=identifier)
        return InMemoryUser(identifier, password=STORED_HASH, roles=["ROLE_USER"])

    @override
    async def refresh_user(self, user: UserInterface) -> UserInterface:
        """Return ``user`` unchanged: the fixture's user never changes."""
        return user

    @override
    def supports_class(self, user_class: type) -> bool:
        """Support the in-memory user this provider builds."""
        return issubclass(user_class, InMemoryUser)

    @override
    async def upgrade_password(
        self,
        user: PasswordAuthenticatedUserInterface,
        new_hashed_password: str,
    ) -> None:
        """Record the rehash the migrating listener asks this store to keep."""
        del user
        self.stored_hashes.append(new_hashed_password)


@final
@as_service
class MigrationTokenHandler(AccessTokenHandlerInterface):
    """Rejects every token: the fixture authenticates nothing through it."""

    __slots__ = ()

    @override
    async def get_user_badge_from(self, access_token: str) -> UserBadge:
        """Reject the token.

        Raises:
            InvalidAccessTokenError: Always; no token opens this fixture.
        """
        del access_token
        raise InvalidAccessTokenError("The token is not known.")
