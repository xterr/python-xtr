"""A format nothing in the serializer reads or writes."""

from __future__ import annotations

from .not_encodable_value_error import NotEncodableValueError

__all__ = ["UnsupportedFormatError"]


class UnsupportedFormatError(NotEncodableValueError):
    """No encoder or decoder of the serializer handles the requested format.

    A value nothing can encode, since nothing encodes that format at all, and
    typed separately because the fix differs: the data is fine, but the
    application asked for a format it never set the serializer up for, or
    misspelled one it did.

    The format is quoted in the message, so one taken from a request cannot
    break the message across lines.

    Attributes:
        format: The format that was asked for, such as ``"json"``.
    """

    format: str

    def __init__(self, format: str) -> None:  # noqa: A002 — the name every serializer call uses.
        """Record the format that was asked for."""
        self.format = format
        super().__init__(f"the format {format!r} is not supported")
