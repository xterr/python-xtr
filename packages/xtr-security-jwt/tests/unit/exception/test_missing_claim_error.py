"""The missing-claim error names its claim and reads as an invalid token."""

from __future__ import annotations

from xtr_security_jwt.exception.jwt_decode_failure_error import JwtDecodeFailureError
from xtr_security_jwt.exception.jwt_failure_error import JwtFailureError
from xtr_security_jwt.exception.missing_claim_error import MissingClaimError


def test_it_derives_from_the_failure_base() -> None:
    assert issubclass(MissingClaimError, JwtFailureError)


def test_it_names_the_claim_and_reads_as_an_invalid_token() -> None:
    error = MissingClaimError("exp")

    assert error.claim == "exp"
    assert error.get_reason() == JwtDecodeFailureError.INVALID_TOKEN
