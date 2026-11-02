"""The serializer was put together or used in a way that cannot work."""

from __future__ import annotations

from .serializer_error import SerializerError

__all__ = ["LogicError"]


class LogicError(SerializerError, RuntimeError):
    """The serializer was put together or used in a way no input could make right.

    A serializer with nothing able to convert the objects it is handed, a class
    hierarchy registered inconsistently: the data is not to blame, the code is,
    and the fix belongs in the application rather than in what it was sent.

    Also a :class:`RuntimeError`, because that is what a worker's own error
    handling already catches.
    """
