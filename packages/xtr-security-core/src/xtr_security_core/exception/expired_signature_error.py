"""A signed hash was presented after the moment it was valid until."""

from __future__ import annotations

from .security_error import SecurityError

__all__ = ["ExpiredSignatureError"]


class ExpiredSignatureError(SecurityError):
    """A signature is sound but past its expiry.

    The secret matched and the covered fields did not change; only the
    moment the hash was valid until has passed. A flow that distinguishes
    this from an invalid signature can tell the caller to start over
    rather than that its link or cookie was never issued.
    """
