"""The invalid-signature error is one of the security family's errors."""

from __future__ import annotations

from xtr_security_core.exception import AuthenticationError, SecurityError

from xtr_security_http.access_token.oidc import InvalidSignatureError


def test_it_is_an_authentication_error() -> None:
    assert issubclass(InvalidSignatureError, AuthenticationError)
    assert issubclass(InvalidSignatureError, SecurityError)


def test_it_carries_its_message_key() -> None:
    error = InvalidSignatureError()

    assert error.get_message_key() == "Invalid token signature."
    assert str(error) == "Invalid token signature."
