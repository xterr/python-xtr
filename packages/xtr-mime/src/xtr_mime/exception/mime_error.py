"""The error every other error of this package derives from."""

from __future__ import annotations

__all__ = ["MimeError"]


class MimeError(Exception):
    """A message could not be built or rendered — catch this to catch them all."""
