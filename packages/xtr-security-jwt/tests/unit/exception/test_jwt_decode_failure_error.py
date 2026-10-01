"""The decode-failure error derives from the base and carries reason and payload."""

from __future__ import annotations

from xtr_security_jwt.exception.jwt_decode_failure_error import JwtDecodeFailureError
from xtr_security_jwt.exception.jwt_failure_error import JwtFailureError


def test_it_derives_from_the_failure_base() -> None:
    assert issubclass(JwtDecodeFailureError, JwtFailureError)


def test_it_carries_its_reason_and_payload() -> None:
    error = JwtDecodeFailureError(
        JwtDecodeFailureError.EXPIRED_TOKEN,
        "gone",
        payload={"sub": "ada"},
    )

    assert error.get_reason() == JwtDecodeFailureError.EXPIRED_TOKEN
    assert error.get_payload() == {"sub": "ada"}
