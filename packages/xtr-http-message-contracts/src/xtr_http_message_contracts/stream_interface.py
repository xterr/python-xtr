"""A stream of bytes a message body is read from and written to."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from typing import BinaryIO

__all__ = ["StreamInterface"]


@runtime_checkable
class StreamInterface(Protocol):
    """A data stream, usually wrapping an open file object.

    This is the body of every message: a cursor over bytes, with the questions
    worth asking before moving it — is it seekable, is it readable, is it
    writable.

    Moving the cursor is awaited. :meth:`read`, :meth:`write`,
    :meth:`get_contents`, :meth:`seek`, :meth:`rewind` and :meth:`close` do
    input and output, so a body can be fed by a socket as readily as by a
    file, without blocking whoever is waiting on it. The questions above only
    report what the stream already holds, so they cost no ``await``.

    Unlike the messages that carry it, a stream is *not* immutable: reading,
    writing and seeking all move the cursor in place.
    """

    async def close(self) -> None:
        """Close the stream and release whatever it was holding open."""
        ...

    def detach(self) -> BinaryIO | None:
        """Hand the underlying file object out and leave the stream unusable.

        Once detached, nothing else on this stream can be relied on; the
        caller owns what came back.

        Returns:
            The file object the stream wrapped, or ``None`` when it wrapped
            none.
        """
        ...

    def get_size(self) -> int | None:
        """Return the size of the stream in bytes, when that is known.

        Returns:
            The size in bytes, or ``None`` when the stream cannot say.
        """
        ...

    def tell(self) -> int:
        """Return where the cursor currently sits.

        Returns:
            The cursor's offset in bytes from the beginning of the stream.

        Raises:
            RuntimeError: When the position cannot be read.
        """
        ...

    def eof(self) -> bool:
        """Tell whether the cursor has reached the end of the stream.

        Returns:
            ``True`` once the end has been reached.
        """
        ...

    def is_seekable(self) -> bool:
        """Tell whether the cursor can be moved.

        Returns:
            ``True`` when :meth:`seek` and :meth:`rewind` work on this stream.
        """
        ...

    async def seek(self, offset: int, whence: int = os.SEEK_SET) -> None:
        """Move the cursor to a position in the stream.

        Args:
            offset: How far to move, in bytes.
            whence: What ``offset`` counts from: ``os.SEEK_SET`` makes it an
                absolute position, ``os.SEEK_CUR`` adds it to where the cursor
                is, ``os.SEEK_END`` adds it to the end of the stream.

        Raises:
            RuntimeError: When the cursor cannot be moved.
        """
        ...

    async def rewind(self) -> None:
        """Move the cursor back to the beginning of the stream.

        Equivalent to ``await seek(0)`` on a seekable stream.

        Raises:
            RuntimeError: When the stream is not seekable, or the cursor
                cannot be moved.
        """
        ...

    def is_writable(self) -> bool:
        """Tell whether data can be written to the stream.

        Returns:
            ``True`` when :meth:`write` works on this stream.
        """
        ...

    async def write(self, data: bytes) -> int:
        """Write bytes at the cursor.

        Args:
            data: What to write.

        Returns:
            How many bytes were written.

        Raises:
            RuntimeError: When the data cannot be written.
        """
        ...

    def is_readable(self) -> bool:
        """Tell whether data can be read from the stream.

        Returns:
            ``True`` when :meth:`read` and :meth:`get_contents` work on this
            stream.
        """
        ...

    async def read(self, length: int) -> bytes:
        """Read up to ``length`` bytes from the cursor.

        Fewer than ``length`` bytes may come back, whenever the underlying
        file object returns fewer.

        Args:
            length: The most to read.

        Returns:
            What was read, or empty bytes when nothing was available.

        Raises:
            RuntimeError: When the stream cannot be read.
        """
        ...

    async def get_contents(self) -> bytes:
        """Read the whole of the stream, from the first byte to the last.

        Rewinds first when the stream is seekable, then reads to the end. On a
        stream that cannot be rewound there is nothing to rewind to, so this
        reads from wherever the cursor sits; :meth:`read` is the way to take a
        measured amount from the current position instead.

        Beware: this may pull a very large amount of data into memory.

        Returns:
            Every byte in the stream.

        Raises:
            RuntimeError: When the stream cannot be read, or reading fails
                part way. An unreadable body is reported rather than answered
                with empty bytes, which would be indistinguishable from an
                empty one.
        """
        ...

    def get_metadata(self, key: str | None = None) -> object:
        """Return what the stream knows about itself.

        The keys are those of the underlying file object — ``mode``,
        ``seekable`` and ``uri`` among them.

        Args:
            key: One entry to look up. ``None`` asks for all of them.

        Returns:
            A mapping of every entry when ``key`` is ``None``; otherwise the
            value under ``key``, or ``None`` when the stream carries no such
            entry.
        """
        ...
