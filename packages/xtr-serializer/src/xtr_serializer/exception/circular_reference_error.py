"""A value that contains itself."""

from __future__ import annotations

from .serializer_error import SerializerError

__all__ = ["CircularReferenceError"]


class CircularReferenceError(SerializerError, RuntimeError):
    """A value contains itself, so it has no plain form to write.

    Plain data is a tree: an object reachable from itself — an order holding a
    line that points back at the order — would never finish being written. It
    is refused rather than cut short, because a value written with a gap in it
    reads back as a different value.

    Also a :class:`RuntimeError`: the cycle is in the objects the application
    built, a mistake to fix in the code, not data from outside to refuse.
    """
