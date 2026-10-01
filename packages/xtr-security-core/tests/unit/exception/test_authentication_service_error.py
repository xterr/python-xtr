"""The authentication-service error is an authentication error."""

from __future__ import annotations

from xtr_security_core.exception import AuthenticationError, AuthenticationServiceError


def test_it_is_an_authentication_error() -> None:
    assert isinstance(AuthenticationServiceError(), AuthenticationError)
