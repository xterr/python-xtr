"""The response-type contract is what a grant hands its tokens to."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, final

from tests.support.response_types import RecordingResponseType
from xtr_security_oauth2_server.response_types.response_type_interface import ResponseTypeInterface

if TYPE_CHECKING:
    from xtr_http_message_contracts import ResponseInterface

    from xtr_security_oauth2_server.entities.access_token_entity_interface import (
        AccessTokenEntityInterface,
    )


@final
class _WithoutRefreshToken:
    """A response type that takes an access token but no refresh token."""

    def set_access_token(self, access_token: AccessTokenEntityInterface) -> None:
        del access_token

    def set_encryption_key(self, key: str, key_type: Literal["plain", "key"]) -> None:
        del key, key_type

    def generate_http_response(self, response: ResponseInterface) -> ResponseInterface:
        return response


def test_a_full_response_type_satisfies_the_contract() -> None:
    response_type: ResponseTypeInterface = RecordingResponseType()

    assert isinstance(response_type, ResponseTypeInterface)


def test_a_response_type_missing_a_method_does_not_satisfy_it() -> None:
    assert not isinstance(_WithoutRefreshToken(), ResponseTypeInterface)
