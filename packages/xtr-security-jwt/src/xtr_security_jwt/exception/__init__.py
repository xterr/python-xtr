"""The errors this library raises, one family under one base.

The signing and verification failures derive from :class:`JwtFailureError`
(itself a :class:`~xtr_security_core.exception.SecurityError`); the errors the
authenticator raises for a request derive from the family's
:class:`~xtr_security_core.exception.AuthenticationError`. One
``except SecurityError`` still catches every one of them.
"""

from __future__ import annotations

from .expired_token_error import ExpiredTokenError
from .invalid_payload_error import InvalidPayloadError
from .invalid_token_error import InvalidTokenError
from .jwt_decode_failure_error import JwtDecodeFailureError
from .jwt_encode_failure_error import JwtEncodeFailureError
from .jwt_failure_error import JwtFailureError
from .missing_claim_error import MissingClaimError
from .missing_token_error import MissingTokenError

__all__ = [
    "ExpiredTokenError",
    "InvalidPayloadError",
    "InvalidTokenError",
    "JwtDecodeFailureError",
    "JwtEncodeFailureError",
    "JwtFailureError",
    "MissingClaimError",
    "MissingTokenError",
]
