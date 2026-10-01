"""A fake access-token handler for the HTTP-edge tests."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_security_http.authenticator.passport.badge.user_badge import UserBadge
from xtr_security_http.exception import InvalidAccessTokenError

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence


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
