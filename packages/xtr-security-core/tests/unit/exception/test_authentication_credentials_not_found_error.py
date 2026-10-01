"""The credentials-not-found error is an authentication error."""

from __future__ import annotations

from xtr_security_core.exception import AuthenticationCredentialsNotFoundError, AuthenticationError


def test_it_is_an_authentication_error() -> None:
    assert isinstance(AuthenticationCredentialsNotFoundError(), AuthenticationError)
