"""The error a malformed declaration raises."""

from __future__ import annotations

from xtr_security_csrf import CsrfError, InvalidArgumentError


def test_it_derives_from_the_package_root() -> None:
    assert issubclass(InvalidArgumentError, CsrfError)


def test_it_is_also_a_value_error() -> None:
    assert issubclass(InvalidArgumentError, ValueError)
