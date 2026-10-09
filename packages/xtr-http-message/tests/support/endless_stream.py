"""A stream that never admits to having reached its end, and will not seek."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_http_message_contracts import StreamInterface

from xtr_http_message import Stream

if TYPE_CHECKING:
    from typing import BinaryIO

__all__ = ["EndlessStream"]


@final
class EndlessStream(StreamInterface):
    """A stream whose ``eof`` answers from its own bookkeeping rather than ours.

    A real one is a stream another implementation of the contract handed over:
    it may count its end differently, or not know it at all, and it may not
    seek — a form parser reading from the wire does neither. Anything that
    copies a stream has to finish against one of these, so this stands in for
    it, and carries its own contract test.

    Everything but the end and the cursor is the work of a real stream
    underneath.
    """

    __slots__ = ("_inner",)

    def __init__(self, content: bytes) -> None:
        """Hold ``content`` behind a real stream.

        Args:
            content: What the stream reads back, once.
        """
        self._inner: StreamInterface = Stream.create(content)

    @override
    def eof(self) -> bool:
        """Never admit to having reached the end.

        Returns:
            Always ``False``.
        """
        return False

    @override
    def is_seekable(self) -> bool:
        """Report that the cursor cannot be moved.

        Returns:
            Always ``False``.
        """
        return False

    @override
    def __bytes__(self) -> bytes:
        """Return everything the stream holds."""
        return bytes(self._inner)

    @override
    def close(self) -> None:
        """Close the stream underneath."""
        self._inner.close()

    @override
    def detach(self) -> BinaryIO | None:
        """Hand out the file object of the stream underneath."""
        return self._inner.detach()

    @override
    def get_size(self) -> int | None:
        """Return the size the stream underneath reports."""
        return self._inner.get_size()

    @override
    def tell(self) -> int:
        """Return where the cursor of the stream underneath sits."""
        return self._inner.tell()

    @override
    def seek(self, offset: int, whence: int = os.SEEK_SET) -> None:
        """Refuse to move the cursor.

        Args:
            offset: Ignored.
            whence: Ignored.

        Raises:
            RuntimeError: Always: this stream does not seek.
        """
        message = "Stream is not seekable"
        raise RuntimeError(message)

    @override
    def rewind(self) -> None:
        """Refuse to move the cursor back.

        Raises:
            RuntimeError: Always: this stream does not seek.
        """
        self.seek(0)

    @override
    def is_writable(self) -> bool:
        """Report what the stream underneath allows."""
        return self._inner.is_writable()

    @override
    def write(self, data: bytes) -> int:
        """Write to the stream underneath."""
        return self._inner.write(data)

    @override
    def is_readable(self) -> bool:
        """Report what the stream underneath allows."""
        return self._inner.is_readable()

    @override
    def read(self, length: int) -> bytes:
        """Read from the stream underneath."""
        return self._inner.read(length)

    @override
    def get_contents(self) -> bytes:
        """Read the rest of the stream underneath."""
        return self._inner.get_contents()

    @override
    def get_metadata(self, key: str | None = None) -> object:
        """Return what the stream underneath knows about itself."""
        return self._inner.get_metadata(key)
