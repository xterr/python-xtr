"""Remember-me fakes: a user provider, a token store, a verifier, a handler."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_security_core.authentication.remember_me.persistent_token import PersistentToken
from xtr_security_core.exception import AuthenticationError, UserNotFoundError

if TYPE_CHECKING:
    from datetime import datetime

    from xtr_http_message_contracts import ServerRequestInterface
    from xtr_security_core.user.user_interface import UserInterface

    from xtr_security_http.remember_me.remember_me_details import RememberMeDetails

__all__ = [
    "RecordingHandler",
    "RecordingTokenProvider",
    "RecordingTokenVerifier",
    "RecordingUserProvider",
]


@final
class RecordingUserProvider:
    """Loads the users a test registered, recording every identifier asked for."""

    __slots__ = ("asked", "users")

    def __init__(self, users: dict[str, UserInterface] | None = None) -> None:
        self.users: dict[str, UserInterface] = dict(users or {})
        self.asked: list[str] = []

    async def load_user_by_identifier(self, identifier: str) -> UserInterface:
        """Return the registered user, or refuse the identifier as unknown.

        Raises:
            UserNotFoundError: When no user was registered for the identifier.
        """
        self.asked.append(identifier)
        user = self.users.get(identifier)
        if user is None:
            raise UserNotFoundError(f'The user "{identifier}" was not registered with the fake.')
        return user

    async def refresh_user(self, user: UserInterface) -> UserInterface:
        """Hand the user back as it is; the remember-me flow never asks."""
        return user

    def supports_class(self, user_class: type) -> bool:
        """Say yes to any class; the remember-me flow never asks."""
        del user_class
        return True


class RecordingTokenProvider:
    """Keeps the tokens a test stored, in memory, recording every call."""

    __slots__: tuple[str, ...] = ("created", "deleted", "series", "updated")

    def __init__(self, tokens: dict[str, PersistentToken] | None = None) -> None:
        self.series: dict[str, PersistentToken] = dict(tokens or {})
        self.created: list[PersistentToken] = []
        self.deleted: list[str] = []
        self.updated: list[tuple[str, str, datetime]] = []

    async def load_token_by_series(self, series: str) -> PersistentToken:
        """Return the stored token of ``series``.

        Raises:
            AuthenticationError: When no token was stored for the series.
        """
        token = self.series.get(series)
        if token is None:
            raise AuthenticationError(f'No token found for the series "{series}".')
        return token

    async def delete_token_by_series(self, series: str) -> None:
        """Drop the stored token of ``series``, recording the delete."""
        self.deleted.append(series)
        _ = self.series.pop(series, None)

    async def update_token(self, series: str, token_value: str, last_used: datetime) -> None:
        """Rotate the stored value of ``series``, recording the update."""
        self.updated.append((series, token_value, last_used))
        token = self.series.get(series)
        if token is None:
            raise AuthenticationError(f'No token found for the series "{series}".')
        self.series[series] = PersistentToken(
            token.get_user_identifier(),
            series,
            token_value,
            last_used,
        )

    async def create_new_token(self, token: PersistentToken) -> None:
        """Store ``token`` as a new series, recording the create."""
        self.created.append(token)
        self.series[token.get_series()] = token


@final
class RecordingTokenVerifier:
    """Answers the token checks a test configured, recording every call."""

    __slots__ = ("accepted", "recorded", "updates")

    def __init__(self, *, accepts: bool = True) -> None:
        self.accepted = accepts
        self.recorded: list[tuple[PersistentToken, str]] = []
        self.updates: list[tuple[PersistentToken, str, datetime]] = []

    async def verify_token(self, token: PersistentToken, token_value: str) -> bool:
        """Record the check, and answer the policy the test configured."""
        self.recorded.append((token, token_value))
        return self.accepted

    async def update_existing_token(
        self,
        token: PersistentToken,
        token_value: str,
        last_used: datetime,
    ) -> None:
        """Record the rotation the handler asked for."""
        self.updates.append((token, token_value, last_used))


@final
class RecordingHandler:
    """Records the cookies a test asked to set, spend and clear."""

    __slots__ = ("cleared", "consumed", "created", "user")

    def __init__(self, user: UserInterface | None = None) -> None:
        self.user = user
        self.created: list[tuple[ServerRequestInterface, UserInterface]] = []
        self.consumed: list[tuple[ServerRequestInterface, RememberMeDetails]] = []
        self.cleared: list[ServerRequestInterface] = []

    async def create_remember_me_cookie(
        self,
        request: ServerRequestInterface,
        user: UserInterface,
    ) -> None:
        """Record the user a login asked to be remembered."""
        self.created.append((request, user))

    async def consume_remember_me_cookie(
        self,
        request: ServerRequestInterface,
        remember_me_details: RememberMeDetails,
    ) -> UserInterface:
        """Record the details a request presented, and answer the configured user.

        Raises:
            AuthenticationError: When no user was configured — the cookie
            spent by a test must name one the fake knows.
        """
        self.consumed.append((request, remember_me_details))
        if self.user is None:
            raise AuthenticationError("The fake handler was configured with no user.")
        return self.user

    async def clear_remember_me_cookie(self, request: ServerRequestInterface) -> None:
        """Record the clearing a test asked for."""
        self.cleared.append(request)
