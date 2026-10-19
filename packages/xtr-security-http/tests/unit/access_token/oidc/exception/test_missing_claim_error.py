"""The missing-claim error is one of the security family's errors."""

from __future__ import annotations

from xtr_security_core.exception import AuthenticationError, SecurityError

from xtr_security_http.access_token.oidc import MissingClaimError


def test_it_is_an_authentication_error() -> None:
    assert issubclass(MissingClaimError, AuthenticationError)
    assert issubclass(MissingClaimError, SecurityError)


def test_it_carries_its_message_key() -> None:
    error = MissingClaimError('"sub" claim not found on OIDC server response.')

    assert error.get_message_key() == "Missing claim."
    assert str(error) == '"sub" claim not found on OIDC server response.'
