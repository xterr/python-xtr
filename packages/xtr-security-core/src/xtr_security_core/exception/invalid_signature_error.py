"""A presented hash does not match what it claims to cover."""

from __future__ import annotations

from .security_error import SecurityError

__all__ = ["InvalidSignatureError"]


class InvalidSignatureError(SecurityError):
    """A signature matches neither the secret nor the fields it claims.

    The hash was forged, or something it covers changed: another user, a
    rotated password, parameters it was not bound with. Nothing about the
    request is sound, so nothing is said about why.
    """
