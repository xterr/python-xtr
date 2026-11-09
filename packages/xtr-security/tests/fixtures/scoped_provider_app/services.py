"""The services the scoped-provider fixture registers: a provider and a checker of the request.

:class:`RequestUnit` stands for the session of the request's unit of work —
one per request — and the provider and the checker take it, the way a
repository takes the session it reads through, so each is built once per
request and never shared with the next. Everything they are asked is written
to :data:`RECORDED`, by the identity of the instance asked, so a test reads
which instance of which request answered.

The fixture user's stored hash is a legacy PBKDF2 one behind a migrating
hasher, so a login also asks the provider to store the rehash.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_dependency_injection import as_service
from xtr_http_foundation import MemorySessionStorage, SessionStorageInterface
from xtr_password_hasher import Pbkdf2PasswordHasher
from xtr_rate_limiter import InMemoryStorage
from xtr_rate_limiter.storage.storage_interface import StorageInterface
from xtr_security_core import InMemoryUser
from xtr_security_core.authentication.remember_me.token_provider_interface import (
    TokenProviderInterface,
)
from xtr_security_core.exception import AuthenticationError, UserNotFoundError
from xtr_security_core.user.password_upgrader_interface import PasswordUpgraderInterface
from xtr_security_core.user.user_checker_interface import UserCheckerInterface
from xtr_security_core.user.user_interface import UserInterface
from xtr_security_core.user.user_provider_interface import UserProviderInterface
from xtr_security_http import UserBadge
from xtr_security_http.access_token.access_token_handler_interface import (
    AccessTokenHandlerInterface,
)

if TYPE_CHECKING:
    from datetime import datetime

    from xtr_password_hasher import PasswordAuthenticatedUserInterface
    from xtr_security_core.authentication.remember_me.persistent_token import PersistentToken
    from xtr_security_core.authentication.token.token_interface import TokenInterface

__all__ = [
    "PASSWORD",
    "RECORDED",
    "STORED_HASH",
    "NamingTokenHandler",
    "Recorded",
    "RequestUnit",
    "ScopedUserChecker",
    "ScopedUserProvider",
    "fixture_login_counters",
    "fixture_remember_me_tokens",
    "fixture_session_storage",
]

#: The plaintext every fixture user's stored hash was made from.
PASSWORD = "secret"

#: The stored hash: PBKDF2, which the migrating hasher verifies and flags for a rehash.
STORED_HASH = Pbkdf2PasswordHasher().hash(PASSWORD)


@final
@dataclass
class Recorded:
    """What the request's services were asked, by the identity of the instance asked."""

    units: list[int] = field(default_factory=list[int])
    providers: list[int] = field(default_factory=list[int])
    loads: list[tuple[str, int]] = field(default_factory=list[tuple[str, int]])
    upgrades: list[int] = field(default_factory=list[int])
    checks: list[tuple[str, int]] = field(default_factory=list[tuple[str, int]])

    def reset(self) -> None:
        """Forget everything recorded, for the next test."""
        self.units.clear()
        self.providers.clear()
        self.loads.clear()
        self.upgrades.clear()
        self.checks.clear()


RECORDED = Recorded()


@final
@as_service(lifetime="scoped")
class RequestUnit:
    """Stands for the session of the request's unit of work: one per request."""

    __slots__ = ()

    def __init__(self) -> None:
        RECORDED.units.append(id(self))


@final
@as_service(lifetime="scoped")
class ScopedUserProvider(UserProviderInterface, PasswordUpgraderInterface):
    """Loads ``ada`` and ``bob`` through the request's unit, and stores their rehashes."""

    __slots__ = ("unit",)

    def __init__(self, unit: RequestUnit) -> None:
        self.unit = unit
        RECORDED.providers.append(id(self))

    @override
    async def load_user_by_identifier(self, identifier: str) -> UserInterface:
        """Return the fixture user ``identifier`` names.

        Raises:
            UserNotFoundError: For anyone but ``ada`` and ``bob``.
        """
        RECORDED.loads.append((identifier, id(self)))
        if identifier not in {"ada", "bob"}:
            raise UserNotFoundError(user_identifier=identifier)
        roles = ["ROLE_USER", "ROLE_ALLOWED_TO_SWITCH"] if identifier == "ada" else ["ROLE_USER"]
        return InMemoryUser(identifier, password=STORED_HASH, roles=roles)

    @override
    async def refresh_user(self, user: UserInterface) -> UserInterface:
        """Return ``user`` unchanged: the fixture's users never change."""
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
        """Record that this instance was asked to store a rehash."""
        del user, new_hashed_password
        RECORDED.upgrades.append(id(self))


@final
@as_service(lifetime="scoped")
class ScopedUserChecker(UserCheckerInterface):
    """Lets every account through, recording which instance checked it."""

    __slots__ = ("unit",)

    def __init__(self, unit: RequestUnit) -> None:
        self.unit = unit

    @override
    async def check_pre_auth(self, user: UserInterface) -> None:
        """Record the pre-authentication check."""
        del user
        RECORDED.checks.append(("pre", id(self)))

    @override
    async def check_post_auth(
        self, user: UserInterface, token: TokenInterface | None = None
    ) -> None:
        """Record the post-authentication check."""
        del user, token
        RECORDED.checks.append(("post", id(self)))


@final
@as_service
class NamingTokenHandler(AccessTokenHandlerInterface):
    """Reads a bearer token as the identifier it names, leaving the load to the firewall."""

    __slots__ = ()

    @override
    async def get_user_badge_from(self, access_token: str) -> UserBadge:
        """Return a badge naming the token's identifier, with no loader of its own."""
        return UserBadge(access_token)


@final
class _RememberMeTokens(TokenProviderInterface):
    """Keeps a persistent remember-me series in this process's memory."""

    __slots__ = ("_tokens",)

    def __init__(self) -> None:
        self._tokens: dict[str, PersistentToken] = {}

    @override
    async def load_token_by_series(self, series: str) -> PersistentToken:
        """Return the series' token.

        Raises:
            AuthenticationError: For a series never stored.
        """
        token = self._tokens.get(series)
        if token is None:
            raise AuthenticationError("No token is stored under the series.")
        return token

    @override
    async def delete_token_by_series(self, series: str) -> None:
        """Forget the series."""
        _ = self._tokens.pop(series, None)

    @override
    async def update_token(self, series: str, token_value: str, last_used: datetime) -> None:
        """Nothing to update: the fixture never spends a stored series."""
        del series, token_value, last_used

    @override
    async def create_new_token(self, token: PersistentToken) -> None:
        """Store the series."""
        self._tokens[token.get_series()] = token


@as_service
def fixture_session_storage() -> SessionStorageInterface:
    """The fixture's session storage: in-memory, as a test's own backend."""
    return MemorySessionStorage()


@as_service
def fixture_login_counters() -> StorageInterface:
    """The fixture's login counters: in-memory, as a test's own backend."""
    return InMemoryStorage()


@as_service(qualifier="fixture_remember_me_tokens", lifetime="scoped")
def fixture_remember_me_tokens(unit: RequestUnit) -> TokenProviderInterface:
    """The persistent remember-me series, over the request's unit like the provider."""
    del unit
    return _RememberMeTokens()
