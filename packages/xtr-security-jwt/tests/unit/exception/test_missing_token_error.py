"""The missing-token error is an authentication error with its public message."""

from __future__ import annotations

from xtr_security_core.exception import AuthenticationError

from xtr_security_jwt.exception.missing_token_error import MissingTokenError


def test_it_is_an_authentication_error() -> None:
    assert issubclass(MissingTokenError, AuthenticationError)


def test_it_carries_its_public_message_key() -> None:
    assert MissingTokenError().get_message_key() == "JWT Token not found"
