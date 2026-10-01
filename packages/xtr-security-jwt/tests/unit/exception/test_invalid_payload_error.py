"""The invalid-payload error is an authentication error naming the absent claim."""

from __future__ import annotations

from xtr_security_core.exception import AuthenticationError

from xtr_security_jwt.exception.invalid_payload_error import InvalidPayloadError


def test_it_is_an_authentication_error() -> None:
    assert issubclass(InvalidPayloadError, AuthenticationError)


def test_it_names_the_absent_claim_in_its_message_key() -> None:
    error = InvalidPayloadError("username")

    assert error.invalid_key == "username"
    assert 'Unable to find key "username"' in error.get_message_key()
