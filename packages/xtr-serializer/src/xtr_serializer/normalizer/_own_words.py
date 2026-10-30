"""The refusal in this package's words that a failed write was raised for."""

from __future__ import annotations

from xtr_serializer.exception import SerializerError

__all__ = ["own_words"]


def own_words(error: BaseException) -> SerializerError | None:
    """Find the refusal in this package's words that ``error`` was raised for, at any depth.

    A serializer refusing so is believed. pydantic raises its own error for it, chaining it, and
    once more for each serializer it was met inside.
    """
    seen: set[int] = set()
    cause: BaseException | None = error
    while cause is not None and id(cause) not in seen:
        if isinstance(cause, SerializerError):
            return cause
        seen.add(id(cause))
        cause = cause.__cause__
    return None
