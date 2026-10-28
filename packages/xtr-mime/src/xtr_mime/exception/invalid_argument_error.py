"""A value handed to this library that cannot be used."""

from __future__ import annotations

from .mime_error import MimeError

__all__ = ["InvalidArgumentError"]


class InvalidArgumentError(MimeError, ValueError):
    """A value handed to this library cannot be used: an unknown charset, an unreadable path.

    Also a :class:`ValueError`, so code that already guards against a bad value catches it
    without knowing this library exists.
    """
