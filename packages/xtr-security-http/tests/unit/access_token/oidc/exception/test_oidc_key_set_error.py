"""The OIDC key-set error is one of the security family's errors."""

from __future__ import annotations

from xtr_security_core.exception import SecurityError

from xtr_security_http.access_token.oidc import OidcKeySetError


def test_it_is_a_security_error() -> None:
    assert issubclass(OidcKeySetError, SecurityError)


def test_it_carries_its_message() -> None:
    error = OidcKeySetError("the keys could not be fetched")

    assert str(error) == "the keys could not be fetched"
