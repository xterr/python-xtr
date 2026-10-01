"""The unsupported-user error is also a type error."""

from __future__ import annotations

from xtr_security_core.exception import SecurityError, UnsupportedUserError


def test_it_is_a_security_error() -> None:
    assert issubclass(UnsupportedUserError, SecurityError)


def test_it_is_a_type_error() -> None:
    assert isinstance(UnsupportedUserError("x"), TypeError)
