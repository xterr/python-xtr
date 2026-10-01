"""The failure base derives from the security error and carries reason and payload."""

from __future__ import annotations

from xtr_security_core.exception import SecurityError

from xtr_security_jwt.exception.jwt_failure_error import JwtFailureError


def test_it_is_a_security_error() -> None:
    assert issubclass(JwtFailureError, SecurityError)


def test_it_carries_its_reason_and_payload() -> None:
    error = JwtFailureError("some_reason", "went wrong", payload={"sub": "ada"})

    assert error.get_reason() == "some_reason"
    assert error.get_payload() == {"sub": "ada"}


def test_it_reports_no_payload_when_none_was_given() -> None:
    assert JwtFailureError("some_reason", "went wrong").get_payload() is None
