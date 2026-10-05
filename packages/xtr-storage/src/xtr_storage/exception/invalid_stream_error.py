"""Something that is not a stream was handed in as one."""

from __future__ import annotations

from .storage_error import StorageError

__all__ = ["InvalidStreamError"]


class InvalidStreamError(StorageError, TypeError):
    """A write was given contents it cannot stream.

    A stream is bytes arriving in pieces — an async iterable, a plain iterable
    or an open binary file. Text is not one: it would have to be encoded, and
    guessing which encoding is how files end up unreadable. The caller encodes
    and hands in bytes.

    Also a :class:`TypeError`, because that is what handing in the wrong kind
    of thing is.

    Attributes:
        received: The name of the type that was handed in.
    """

    received: str

    def __init__(self, received: str) -> None:
        """Record what was handed in instead of a stream."""
        self.received = received
        super().__init__(f"a stream must be an iterable of bytes or a binary file, got {received}")
