"""The shape of an access-token type."""

from __future__ import annotations

from typing import final

from xtr_security_http.oauth2 import BearerTokenType
from xtr_security_http.oauth2.access_token_type import AccessTokenTypeInterface


@final
class _TokenType:
    """A token type answering every member of the interface."""

    def get_token_type(self) -> str:
        return "example"

    def check_token_response(self, token_response: dict[str, object]) -> None:
        del token_response

    def prepare_token_request(self, url: str, options: dict[str, object]) -> dict[str, object]:
        del url
        return options

    def present_token(
        self,
        access_token: str,
        method: str,
        url: str,
        options: dict[str, object],
    ) -> dict[str, object]:
        del access_token, method, url
        return options

    def on_response(self, response: object, url: str) -> bool:
        del response, url
        return False


def test_a_type_answering_every_member_is_an_access_token_type() -> None:
    assert isinstance(_TokenType(), AccessTokenTypeInterface)


def test_the_bearer_type_is_an_access_token_type() -> None:
    assert isinstance(BearerTokenType(), AccessTokenTypeInterface)
