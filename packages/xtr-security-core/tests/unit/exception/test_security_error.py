"""The package base error is the root every other error derives from."""

from __future__ import annotations

from xtr_security_core.exception import (
    AccessDeniedError,
    AuthenticationError,
    InvalidArgumentError,
    SecurityError,
    UnsupportedUserError,
)


def test_it_is_an_exception() -> None:
    assert issubclass(SecurityError, Exception)


def test_every_error_derives_from_it() -> None:
    for error_type in (
        AuthenticationError,
        AccessDeniedError,
        UnsupportedUserError,
        InvalidArgumentError,
    ):
        assert issubclass(error_type, SecurityError)
