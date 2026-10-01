"""The invalid-access-token error is an authentication error."""

from __future__ import annotations

from xtr_security_core.exception import AuthenticationError

from xtr_security_http.exception import InvalidAccessTokenError


def test_it_is_an_authentication_error() -> None:
    assert isinstance(InvalidAccessTokenError(), AuthenticationError)
