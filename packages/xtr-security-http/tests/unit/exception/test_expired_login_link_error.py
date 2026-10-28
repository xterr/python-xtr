"""The expired-login-link error: a sound link, followed too late."""

from __future__ import annotations

from xtr_security_core.exception import ExpiredSignatureError

from xtr_security_http.exception import ExpiredLoginLinkError, InvalidLoginLinkErrorInterface


def test_it_is_an_expired_signature_error() -> None:
    assert isinstance(ExpiredLoginLinkError("Login link has expired."), ExpiredSignatureError)


def test_it_wears_the_marker_the_flow_catches() -> None:
    error = ExpiredLoginLinkError("Login link has expired.")
    assert isinstance(error, InvalidLoginLinkErrorInterface)
