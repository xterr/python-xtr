"""The expired-signature error is a sound signature past its time."""

from __future__ import annotations

from xtr_security_core.exception import ExpiredSignatureError, SecurityError


def test_it_is_a_security_error() -> None:
    assert issubclass(ExpiredSignatureError, SecurityError)


def test_it_carries_its_reason() -> None:
    error = ExpiredSignatureError("Signature has expired.")

    assert str(error) == "Signature has expired."
