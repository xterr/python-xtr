"""The recording response type really satisfies the contract it stands in for."""

from __future__ import annotations

from xtr_http_message import Response

from tests.support.entities import AccessToken, RefreshToken, make_client
from tests.support.response_types import RecordingResponseType
from xtr_security_oauth2_server.response_types.response_type_interface import ResponseTypeInterface


def test_it_satisfies_the_response_type_contract() -> None:
    assert isinstance(RecordingResponseType(), ResponseTypeInterface)


def test_it_starts_holding_nothing() -> None:
    response_type = RecordingResponseType()

    assert response_type.access_token is None
    assert response_type.refresh_token is None
    assert response_type.encryption_key is None


def test_it_keeps_the_access_token_it_was_given() -> None:
    response_type = RecordingResponseType()
    token = AccessToken()
    token.set_client(make_client())

    response_type.set_access_token(token)

    assert response_type.access_token is token


def test_it_keeps_the_refresh_token_it_was_given() -> None:
    response_type = RecordingResponseType()
    token = RefreshToken()

    response_type.set_refresh_token(token)

    assert response_type.refresh_token is token


def test_it_keeps_the_encryption_key_it_was_given() -> None:
    response_type = RecordingResponseType()

    response_type.set_encryption_key("a" * 44, "key")

    assert response_type.encryption_key == ("a" * 44, "key")


def test_it_answers_two_hundred() -> None:
    assert RecordingResponseType().generate_http_response(Response()).get_status_code() == 200
