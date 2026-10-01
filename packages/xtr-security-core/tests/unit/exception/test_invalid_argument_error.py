"""The invalid-argument error is also a value error."""

from __future__ import annotations

from xtr_security_core.exception import InvalidArgumentError, SecurityError


def test_it_is_a_security_error() -> None:
    assert issubclass(InvalidArgumentError, SecurityError)


def test_it_is_a_value_error() -> None:
    assert isinstance(InvalidArgumentError("x"), ValueError)
