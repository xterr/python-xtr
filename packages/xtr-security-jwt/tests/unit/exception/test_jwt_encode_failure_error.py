"""The encode-failure error derives from the base and carries its reason."""

from __future__ import annotations

from xtr_security_jwt.exception.jwt_encode_failure_error import JwtEncodeFailureError
from xtr_security_jwt.exception.jwt_failure_error import JwtFailureError


def test_it_derives_from_the_failure_base() -> None:
    assert issubclass(JwtEncodeFailureError, JwtFailureError)


def test_it_carries_its_reason() -> None:
    error = JwtEncodeFailureError(JwtEncodeFailureError.INVALID_CONFIG, "bad")

    assert error.get_reason() == JwtEncodeFailureError.INVALID_CONFIG


def test_a_failure_without_a_payload_reports_none() -> None:
    assert JwtEncodeFailureError(JwtEncodeFailureError.UNSIGNED_TOKEN, "bad").get_payload() is None
