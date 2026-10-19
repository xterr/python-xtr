"""A fake access-token handler for the HTTP-edge tests."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_security_http.authenticator.passport.badge.user_badge import UserBadge
from xtr_security_http.exception import InvalidAccessTokenError

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from xtr_http_message_contracts import ServerRequestInterface
    from xtr_security_core.exception import AuthenticationError


@final
class FakeAccessTokenHandler:
    """Maps a known token string to the user (and scopes) it proves."""

    def __init__(self, tokens: Mapping[str, tuple[str, Sequence[str]]]) -> None:
        self._tokens = dict(tokens)

    async def get_user_badge_from(self, access_token: str) -> UserBadge:
        if access_token not in self._tokens:
            raise InvalidAccessTokenError("The token is not known.")
        identifier, scopes = self._tokens[access_token]
        attributes: dict[str, object] = {"scope": list(scopes)} if scopes else {}
        return UserBadge(identifier, attributes=attributes)


@final
class FakeSenderConstraint:
    """A sender constraint that records what it weighed, and answers as configured.

    ``check`` records the request, the token and the claims it was handed,
    and raises ``refusal`` when one is configured — the proof the request
    did not check out. ``get_challenge`` records the error it was asked
    about and answers the configured scheme and parameters.
    """

    def __init__(
        self,
        scheme: str = "DPoP",
        parameters: Mapping[str, str] | None = None,
        refusal: AuthenticationError | None = None,
    ) -> None:
        self.scheme = scheme
        self.parameters = dict(parameters or {})
        self.refusal = refusal
        self.checked: tuple[ServerRequestInterface, str, Mapping[str, object]] | None = None
        self.challenged: list[AuthenticationError | None] = []

    async def check(
        self,
        request: ServerRequestInterface,
        access_token: str,
        claims: Mapping[str, object],
    ) -> None:
        """Record what was weighed, and refuse when configured to."""
        self.checked = (request, access_token, dict(claims))
        if self.refusal is not None:
            raise self.refusal

    def get_challenge(self, error: AuthenticationError | None) -> tuple[str, Mapping[str, str]]:
        """Record the error answered, and answer the configured challenge."""
        self.challenged.append(error)
        return self.scheme, dict(self.parameters)
