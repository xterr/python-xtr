"""What every response type is handed, and what it refuses to answer without."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

import pytest
from typing_extensions import override
from xtr_http_message import Response

from tests.support.encryption import ENCRYPTION_KEY
from tests.support.entities import AccessToken, RefreshToken, make_client
from tests.support.messages import body_of
from xtr_security_oauth2_server.exception.invalid_argument_error import InvalidArgumentError
from xtr_security_oauth2_server.response_types.abstract_response_type import AbstractResponseType
from xtr_security_oauth2_server.response_types.response_type_interface import ResponseTypeInterface

if TYPE_CHECKING:
    from xtr_http_message_contracts import ResponseInterface

    from xtr_security_oauth2_server.entities.access_token_entity_interface import (
        AccessTokenEntityInterface,
    )
    from xtr_security_oauth2_server.entities.refresh_token_entity_interface import (
        RefreshTokenEntityInterface,
    )


@final
class _NamingResponseType(AbstractResponseType):
    """Answers with the identifier of whatever it was handed."""

    @override
    def generate_http_response(self, response: ResponseInterface) -> ResponseInterface:
        _ = response.get_body().write(self._access_token_or_fail().get_identifier().encode())

        return response

    def issued_refresh_token(self) -> RefreshTokenEntityInterface | None:
        """Hand a test what a subclass reads off the protected field."""
        return self._refresh_token

    def held_access_token(self) -> AccessTokenEntityInterface:
        """Hand a test what a subclass reads off the protected accessor."""
        return self._access_token_or_fail()


def _access_token(identifier: str = "token-1") -> AccessToken:
    token = AccessToken()
    token.set_client(make_client())
    token.set_identifier(identifier)

    return token


def test_a_concrete_response_type_satisfies_the_contract() -> None:
    assert ResponseTypeInterface in AbstractResponseType.__mro__
    assert isinstance(_NamingResponseType(), ResponseTypeInterface)


def test_it_hands_a_subclass_the_access_token_it_was_given() -> None:
    response_type = _NamingResponseType()
    token = _access_token()

    response_type.set_access_token(token)

    assert response_type.held_access_token() is token


def test_asking_for_the_access_token_before_one_is_set_names_the_setter() -> None:
    response_type = _NamingResponseType()

    with pytest.raises(InvalidArgumentError, match="set_access_token"):
        _ = response_type.held_access_token()


def test_a_response_type_handed_no_refresh_token_reports_none() -> None:
    assert _NamingResponseType().issued_refresh_token() is None


def test_it_hands_a_subclass_the_refresh_token_it_was_given() -> None:
    response_type = _NamingResponseType()
    token = RefreshToken()

    response_type.set_refresh_token(token)

    assert response_type.issued_refresh_token() is token


def test_it_seals_and_reads_back_a_payload_with_the_key_it_was_given() -> None:
    response_type = _NamingResponseType()
    response_type.set_encryption_key(ENCRYPTION_KEY, "key")

    sealed = response_type.encrypt({"refresh_token_id": "token-1"})

    assert response_type.decrypt(sealed) == {"refresh_token_id": "token-1"}


def test_the_answer_is_built_on_the_response_it_was_handed() -> None:
    response_type = _NamingResponseType()
    response_type.set_access_token(_access_token("token-9"))

    answer = response_type.generate_http_response(Response().with_header("x-trace", "1"))

    assert body_of(answer) == "token-9"
    assert answer.get_header_line("x-trace") == "1"
