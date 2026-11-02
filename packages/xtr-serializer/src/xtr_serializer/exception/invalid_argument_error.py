"""An argument handed to the serializer cannot be used."""

from __future__ import annotations

from .serializer_error import SerializerError

__all__ = ["InvalidArgumentError"]


class InvalidArgumentError(SerializerError, ValueError):
    """An argument the serializer was given cannot be used, whatever data comes next.

    It is about how the serializer is called or configured, not about what it
    converts: data that does not fit is an
    :class:`UnexpectedValueError <xtr_serializer.exception.UnexpectedValueError>`.

    Also a :class:`ValueError`, so code that already guards what it passes with
    ``except ValueError`` catches it without learning a new exception.
    """
