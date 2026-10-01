"""The failure raised when a token cannot be signed."""

from __future__ import annotations

from typing import Final

from .jwt_failure_error import JwtFailureError

__all__ = ["JwtEncodeFailureError"]


class JwtEncodeFailureError(JwtFailureError):
    """Signing a set of claims into a token failed.

    Its ``reason`` is :data:`INVALID_CONFIG` when the signing key or algorithm
    the provider was built with cannot produce a signature, or
    :data:`UNSIGNED_TOKEN` when the provider returned a token it did not sign.
    """

    #: The signing configuration — key or algorithm — cannot sign.
    INVALID_CONFIG: Final[str] = "invalid_config"

    #: The provider returned a token without a signature.
    UNSIGNED_TOKEN: Final[str] = "unsigned_token"  # noqa: S105 -- a reason code, not a secret
