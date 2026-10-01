"""The invalid-token error is an authentication error with its public message."""

from __future__ import annotations

from xtr_security_core.exception import AuthenticationError

from xtr_security_jwt.exception.invalid_token_error import InvalidTokenError


def test_it_is_an_authentication_error() -> None:
    assert issubclass(InvalidTokenError, AuthenticationError)


def test_it_carries_its_public_message_key() -> None:
    assert InvalidTokenError().get_message_key() == "Invalid JWT Token"
