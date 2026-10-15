"""The invalid-signature error is a hash that matches nothing it claims."""

from __future__ import annotations

from xtr_security_core.exception import InvalidSignatureError, SecurityError


def test_it_is_a_security_error() -> None:
    assert issubclass(InvalidSignatureError, SecurityError)


def test_it_carries_its_reason() -> None:
    error = InvalidSignatureError("Invalid or expired signature.")

    assert str(error) == "Invalid or expired signature."
