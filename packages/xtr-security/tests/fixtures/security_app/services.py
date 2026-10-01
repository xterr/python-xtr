"""The services the served fixture registers: a token handler and a user store."""

from __future__ import annotations

from typing import final

from typing_extensions import override
from xtr_dependency_injection import as_service
from xtr_security_core import InMemoryUser
from xtr_security_core.user.user_interface import UserInterface
from xtr_security_core.user.user_provider_interface import UserProviderInterface
from xtr_security_http import UserBadge
from xtr_security_http.access_token.access_token_handler_interface import (
    AccessTokenHandlerInterface,
)
from xtr_security_http.exception import InvalidAccessTokenError

__all__ = ["FixtureTokenHandler", "FixtureUserProvider"]

_USERS = {
    "good": ("alice", ["ROLE_USER"], ["books:read"]),
    "admin": ("root", ["ROLE_USER", "ROLE_ADMIN"], ["books:read", "reports:write"]),
}


@final
@as_service
class FixtureUserProvider(UserProviderInterface):
    """Loads the fixture's users by identifier."""

    __slots__ = ()

    @override
    async def load_user_by_identifier(self, identifier: str) -> UserInterface:
        """Return the fixture user for ``identifier``."""
        roles = ["ROLE_ADMIN", "ROLE_USER"] if identifier == "root" else ["ROLE_USER"]
        return InMemoryUser(identifier, roles=roles)

    @override
    def supports_class(self, user_class: type) -> bool:
        """Support the in-memory user this provider builds."""
        return issubclass(user_class, InMemoryUser)


@final
@as_service
class FixtureTokenHandler(AccessTokenHandlerInterface):
    """Validates the fixture's bearer tokens into a user badge with scopes."""

    __slots__ = ()

    @override
    async def get_user_badge_from(self, access_token: str) -> UserBadge:
        """Return the badge a known token proves, or reject an unknown one.

        Raises:
            InvalidAccessTokenError: When the token is not one the fixture knows.
        """
        known = _USERS.get(access_token)
        if known is None:
            raise InvalidAccessTokenError("The token is not known.")
        identifier, roles, scopes = known

        def load(loaded: str) -> UserInterface:
            return InMemoryUser(loaded, roles=roles)

        return UserBadge(identifier, user_loader=load, attributes={"scope": scopes})
