"""The invalid-login-link error: a refused link, and a runtime failure."""

from __future__ import annotations

from xtr_security_core.exception import SecurityError

from xtr_security_http.exception import (
    InvalidLoginLinkError,
    InvalidLoginLinkErrorInterface,
)


def test_it_is_a_security_error_and_a_runtime_failure() -> None:
    error = InvalidLoginLinkError('Missing "user" parameter.')

    assert isinstance(error, SecurityError)
    assert isinstance(error, RuntimeError)


def test_it_wears_the_marker_the_flow_catches() -> None:
    assert isinstance(InvalidLoginLinkError("refused"), InvalidLoginLinkErrorInterface)


def test_a_bare_object_does_not_wear_the_marker() -> None:
    assert not isinstance(object(), InvalidLoginLinkErrorInterface)
