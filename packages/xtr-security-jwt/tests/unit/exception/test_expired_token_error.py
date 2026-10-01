"""The expired-token error is an authentication error with its public message."""

from __future__ import annotations

from xtr_security_core.exception import AuthenticationError

from xtr_security_jwt.exception.expired_token_error import ExpiredTokenError


def test_it_is_an_authentication_error() -> None:
    assert issubclass(ExpiredTokenError, AuthenticationError)


def test_it_carries_its_public_message_key() -> None:
    assert ExpiredTokenError().get_message_key() == "Expired JWT Token"
