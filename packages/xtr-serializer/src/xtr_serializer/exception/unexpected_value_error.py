"""A value cannot become what the serializer was asked to make of it."""

from __future__ import annotations

from .serializer_error import SerializerError

__all__ = ["UnexpectedValueError"]


class UnexpectedValueError(SerializerError, ValueError):
    """A value, or the data read for one, cannot become what the serializer was asked for.

    The family of errors about the data itself, as opposed to how the serializer
    was set up: text that is not valid in its format, a value with no exact plain
    form, data that does not fit the type it is read into. Catch it to tell
    whoever sent the data that it was refused; the subclasses say at which step.

    Also a :class:`ValueError`, the error Python raises for a value of the right
    type with the wrong content.
    """
