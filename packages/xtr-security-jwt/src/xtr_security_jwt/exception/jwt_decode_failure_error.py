"""The failure raised when a token cannot be verified."""

from __future__ import annotations

from typing import Final

from .jwt_failure_error import JwtFailureError

__all__ = ["JwtDecodeFailureError"]


class JwtDecodeFailureError(JwtFailureError):
    """Reading a token back into claims failed.

    Its ``reason`` tells the three apart: :data:`INVALID_TOKEN` for a token that
    could not be read or whose issued-at time is in the future,
    :data:`EXPIRED_TOKEN` for one past its expiry, and :data:`UNVERIFIED_TOKEN`
    for one whose signature does not verify against any known key.
    """

    #: The token is malformed, or its ``iat`` lies in the future.
    INVALID_TOKEN: Final[str] = "invalid_token"  # noqa: S105 -- a reason code, not a secret

    #: The token's signature does not verify against any known key.
    UNVERIFIED_TOKEN: Final[str] = "unverified_token"  # noqa: S105 -- a reason code, not a secret

    #: The token is past its ``exp`` expiry time.
    EXPIRED_TOKEN: Final[str] = "expired_token"  # noqa: S105 -- a reason code, not a secret
