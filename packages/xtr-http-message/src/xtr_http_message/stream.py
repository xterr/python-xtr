"""A message body: a cursor over bytes, wrapping an open binary file object."""

from __future__ import annotations

import io
import os
from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_http_message_contracts import StreamInterface

from .exception import StreamError

if TYPE_CHECKING:
    from typing import BinaryIO

__all__ = ["Stream"]

_READ_WRITE = "rb+"
_READ = "rb"
_WRITE = "wb"


def _attribute(obj: object, name: str) -> object:
    """Return an attribute of a file object, or ``None`` when it has none.

    File objects differ in what they carry: one opened from a path has a
    ``name``, one over a bytes buffer has neither that nor a ``mode``. Asking
    for either has to be allowed to come back empty.
    """
    return getattr(obj, name, None)


def _mode(stream: BinaryIO, readable: bool, writable: bool) -> str:
    """Return how a file object was opened, as a mode string.

    A file opened from a path reports its own mode. A buffer over bytes has
    none to report, so the mode is read back off what it will let us do.

    Args:
        stream: The file object.
        readable: Whether the stream reads, as the stream itself sees it.
        writable: Whether the stream writes, as the stream itself sees it.

    Returns:
        The mode the file object was opened in, or one that says what it
        allows.
    """
    mode = _attribute(stream, "mode")
    if isinstance(mode, str):
        return mode
    if readable:
        return _READ_WRITE if writable else _READ
    return _WRITE


def _file_name(stream: BinaryIO) -> str | None:
    """Return the path a file object was opened on, when it has one.

    A file object opened on a descriptor reports that number rather than a
    path, and one over a bytes buffer reports nothing; both read as ``None``.
    """
    name = _attribute(stream, "name")
    return name if isinstance(name, str) else None


@final
class Stream(StreamInterface):
    """A stream over an open binary file object.

    Build one with :meth:`create` rather than by hand: that is the entry point
    that takes the payload in any of the three shapes a body arrives in —
    bytes, an open file object, or a stream that is already one of these.

    The payload is bytes throughout. A body may be an image or a compressed
    archive, so there is no encoding to guess at, and
    ``await stream.get_contents()`` is what reads the whole of one.

    Moving bytes is awaited: :meth:`read`, :meth:`write`,
    :meth:`get_contents`, :meth:`seek`, :meth:`rewind` and :meth:`close` do
    input and output. The methods that only report what the stream already
    holds cost no ``await``.

    Unlike the messages that carry it, a stream is not immutable: reading,
    writing and seeking all move its cursor in place.
    """

    __slots__ = ("_at_end", "_size", "_stream")

    def __init__(self, body: BinaryIO) -> None:
        """Wrap an open binary file object.

        Args:
            body: The file object to read from and write to. The stream takes
                it over: closing the stream closes it.
        """
        self._stream: BinaryIO | None = body
        self._size: int | None = None
        self._at_end: bool = False

    @classmethod
    def create(cls, body: bytes | BinaryIO | StreamInterface = b"") -> StreamInterface:
        """Return a stream over ``body``, whatever shape it arrived in.

        Args:
            body: The payload. Bytes are held in memory; an open binary file
                object is taken over as it is; a stream that is already one
                comes straight back, since wrapping it again would only add a
                cursor over a cursor.

        Returns:
            The stream.
        """
        if isinstance(body, bytes):
            return cls(io.BytesIO(body))
        if isinstance(body, StreamInterface):
            return body
        return cls(body)

    @override
    async def close(self) -> None:
        """Close the file object and let go of it."""
        if self._stream is not None:
            self._stream.close()
            _ = self.detach()

    @override
    def detach(self) -> BinaryIO | None:
        """Hand the file object out and leave the stream unusable.

        Returns:
            The file object the stream wrapped, or ``None`` when it has
            already been handed out.
        """
        detached = self._stream
        self._stream = None
        self._size = None
        self._at_end = False
        return detached

    @override
    def get_size(self) -> int | None:
        """Return the size of the stream in bytes, when that is knowable.

        The size is measured by seeking to the end and back, so it is always
        current; it is then remembered until the next write.

        Returns:
            The size in bytes, or ``None`` when the stream is detached or
            cannot be seeked over.
        """
        if self._size is not None:
            return self._size

        stream = self._stream
        if stream is None or not self.is_seekable():
            return None

        here = stream.tell()
        self._size = stream.seek(0, os.SEEK_END)
        _ = stream.seek(here, os.SEEK_SET)

        return self._size

    @override
    def tell(self) -> int:
        """Return where the cursor currently sits.

        Returns:
            The cursor's offset in bytes from the beginning of the stream.

        Raises:
            StreamError: When the stream is detached, or the position cannot
                be read.
        """
        stream = self._require_stream()
        try:
            return stream.tell()
        except (OSError, ValueError) as error:
            message = f"Unable to determine stream position: {error}"
            raise StreamError(message) from error

    @override
    def eof(self) -> bool:
        """Tell whether reading has reached the end of the stream.

        It reports that a read *found* the end, not merely that the cursor
        sits there: a stream just written to is at its end but has not reached
        it. A seek puts that back to not-yet.

        A read coming back with less than was asked for is not in itself the
        end either — a pipe or a socket answers with whatever has arrived —
        unless the cursor can be asked, and has reached the size.

        Returns:
            ``True`` once a read has reached the end, and for a detached
            stream.
        """
        return self._stream is None or self._at_end

    @override
    def is_seekable(self) -> bool:
        """Tell whether the cursor can be moved.

        Returns:
            ``True`` when the file object seeks and the stream still holds it.
        """
        stream = self._stream

        return stream is not None and not stream.closed and stream.seekable()

    @override
    async def seek(self, offset: int, whence: int = os.SEEK_SET) -> None:
        """Move the cursor to a position in the stream.

        Args:
            offset: How far to move, in bytes.
            whence: What ``offset`` counts from: ``os.SEEK_SET``,
                ``os.SEEK_CUR`` or ``os.SEEK_END``.

        Raises:
            StreamError: When the stream is detached, is not seekable, or the
                cursor cannot be moved there.
        """
        stream = self._require_stream()
        if not self.is_seekable():
            raise StreamError("Stream is not seekable")

        try:
            _ = stream.seek(offset, whence)
        except (OSError, ValueError) as error:
            message = f'Unable to seek to stream position "{offset}" with whence {whence}'
            raise StreamError(message) from error

        self._at_end = False

    @override
    async def rewind(self) -> None:
        """Move the cursor back to the beginning of the stream.

        Raises:
            StreamError: When the stream is detached or not seekable.
        """
        await self.seek(0)

    @override
    def is_writable(self) -> bool:
        """Tell whether data can be written to the stream.

        Returns:
            ``True`` when the file object accepts writes and the stream still
            holds it.
        """
        stream = self._stream

        return stream is not None and not stream.closed and stream.writable()

    @override
    async def write(self, data: bytes) -> int:
        """Write bytes at the cursor.

        Args:
            data: What to write.

        Returns:
            How many bytes were written.

        Raises:
            StreamError: When the stream is detached, is not writable, or the
                write fails.
        """
        stream = self._require_stream()
        if not self.is_writable():
            raise StreamError("Cannot write to a non-writable stream")

        # Whatever the size was, it is not that any more.
        self._size = None

        try:
            return stream.write(data)
        except (OSError, ValueError) as error:
            message = f"Unable to write to stream: {error}"
            raise StreamError(message) from error

    @override
    def is_readable(self) -> bool:
        """Tell whether data can be read from the stream.

        Returns:
            ``True`` when the file object serves reads and the stream still
            holds it.
        """
        stream = self._stream

        return stream is not None and not stream.closed and stream.readable()

    @override
    async def read(self, length: int) -> bytes:
        """Read up to ``length`` bytes from the cursor.

        Args:
            length: The most to read.

        Returns:
            What was read, or empty bytes at the end of the stream.

        Raises:
            StreamError: When the stream is detached, is not readable, or the
                read fails.
        """
        stream = self._require_stream()
        if not self.is_readable():
            raise StreamError("Cannot read from non-readable stream")

        try:
            chunk = stream.read(length)
        except (OSError, ValueError) as error:
            message = f"Unable to read from stream: {error}"
            raise StreamError(message) from error

        if chunk == b"":
            self._at_end = True
        elif len(chunk) < length and self.is_seekable():
            # A read of a pipe, a socket or any unbuffered source comes back
            # with whatever has arrived, which says nothing about the end. A
            # stream whose cursor moves can be asked instead: the end is where
            # the cursor has reached the size.
            self._at_end = self.tell() == self.get_size()

        return chunk

    @override
    async def get_contents(self) -> bytes:
        """Read the whole of the stream, from the first byte to the last.

        Rewinds first when the cursor can be moved, then reads to the end. A
        stream that cannot be rewound has nothing to rewind to, so that one is
        read from wherever its cursor sits; :meth:`read` is the way to take a
        measured amount from the current position instead.

        Returns:
            Every byte in the stream.

        Raises:
            StreamError: When the stream is detached, cannot be rewound after
                saying it can, or cannot be read. An unreadable body is
                reported rather than answered with empty bytes, which would be
                indistinguishable from an empty one.
        """
        stream = self._require_stream()
        if self.is_seekable():
            await self.seek(0)

        try:
            contents = stream.read()
        except (OSError, ValueError) as error:
            message = f"Unable to read stream contents: {error}"
            raise StreamError(message) from error

        self._at_end = True

        return contents

    @override
    def get_metadata(self, key: str | None = None) -> object:
        """Return what the stream knows about itself.

        Three entries: ``mode``, how the file object was opened; ``seekable``,
        whether its cursor moves; and ``uri``, the path it was opened on when
        it has one.

        Args:
            key: One entry to look up. ``None`` asks for all of them.

        Returns:
            A fresh mapping of every entry when ``key`` is ``None``, empty for
            a detached stream; otherwise the value under ``key``, or ``None``
            when there is no such entry.
        """
        stream = self._stream
        if stream is None:
            return None if key is not None else {}

        metadata: dict[str, object] = {
            "mode": _mode(stream, readable=self.is_readable(), writable=self.is_writable()),
            "seekable": self.is_seekable(),
            "uri": _file_name(stream),
        }

        return metadata if key is None else metadata.get(key)

    def _require_stream(self) -> BinaryIO:
        """Return the file object, refusing to work once it has been handed out.

        Returns:
            The file object the stream wraps.

        Raises:
            StreamError: When the stream is detached.
        """
        if self._stream is None:
            raise StreamError("Stream is detached")

        return self._stream
