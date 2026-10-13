"""The error every other error of this package derives from."""

from __future__ import annotations

__all__ = ["HttpFoundationError"]


class HttpFoundationError(Exception):
    """Something asked of this library that it cannot do — catch this to catch them all."""
