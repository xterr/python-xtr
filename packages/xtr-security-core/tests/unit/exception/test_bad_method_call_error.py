"""The bad-method-call error is a security error."""

from __future__ import annotations

from xtr_security_core.exception import BadMethodCallError, SecurityError


def test_it_is_a_security_error() -> None:
    assert issubclass(BadMethodCallError, SecurityError)
