"""A body stream that reads its bytes once, on its first read.

A request built over a connection must hand out a stream, but nobody
has read that connection's body until something asks to — reading it
eagerly is exactly what a lazy request may not do. This stream stands
in for the body until the first read, then materialises the whole of it
once and serves every later read out of the buffer: seekable and
rewindable, so a reader that inspects can rewind for whoever reads
after it.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_http_message_contracts import StreamInterface

from .stream import Stream

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from typing import BinaryIO

__all__ = ["LazyStream"]


@final
class LazyStream(StreamInterface):
    """A body stream that reads its bytes once, on its first read.

    Built with a coroutine that returns the buffered body — one that
    reads the connection and parses it per its content type — and holds
    nothing until the first :meth:`read` or :meth:`get_contents` calls
    it. From then on it is a plain view over the buffer, and every
    question the contract asks of an unread stream is answered for the
    buffer it will be.
    """

    __slots__ = ("_buffered", "_materialise")

    def __init__(self, materialise: Callable[[], Awaitable[bytes]]) -> None:
        """Read the body through ``materialise``, when anything first asks to.

        Args:
            materialise: Reads the whole body and returns its bytes.
        """
        self._materialise = materialise
        self._buffered: StreamInterface | None = None

    @property
    def materialised(self) -> bool:
        """Tell whether the body has been read into memory."""
        return self._buffered is not None

    async def _held(self) -> StreamInterface:
        """Return the buffered body, reading it off the connection if nothing has yet."""
        if self._buffered is None:
            self._buffered = Stream.create(await self._materialise())
        return self._buffered

    @override
    async def close(self) -> None:
        """Close the buffer, if there is one to close.

        An unread body holds nothing open, so closing one before the
        first read is not a read: it is a no-op, and the next reader
        still gets the bytes off the connection.
        """
        if self._buffered is not None:
            await self._buffered.close()

    @override
    def detach(self) -> BinaryIO | None:
        """Hand out the buffer's file object, or ``None`` while there is none."""
        return self._buffered.detach() if self._buffered is not None else None

    @override
    def get_size(self) -> int | None:
        """Return the size of the buffered body, or ``None`` before there is one."""
        return self._buffered.get_size() if self._buffered is not None else None

    @override
    def tell(self) -> int:
        """Return where the cursor sits: the first byte, until there is a buffer."""
        return self._buffered.tell() if self._buffered is not None else 0

    @override
    def eof(self) -> bool:
        """Tell whether a read reached the end: no read has, until there is a buffer."""
        return self._buffered.eof() if self._buffered is not None else False

    @override
    def is_seekable(self) -> bool:
        """Tell whether the cursor moves: the buffer it will be is over bytes in memory."""
        return True

    @override
    async def seek(self, offset: int, whence: int = os.SEEK_SET) -> None:
        """Move the cursor, materialising the body if nothing has read it yet.

        Raises:
            StreamError: When the buffer cannot be moved, once there is one.
        """
        await (await self._held()).seek(offset, whence)

    @override
    async def rewind(self) -> None:
        """Move the cursor back to the first byte, materialising if nothing has read."""
        await (await self._held()).rewind()

    @override
    def is_writable(self) -> bool:
        """Tell whether bytes can be written to the buffer: it is a buffer, so yes."""
        return True

    @override
    async def write(self, data: bytes) -> int:
        """Write at the cursor, materialising the body if nothing has read it yet.

        Raises:
            StreamError: When the buffer cannot be written to.
        """
        return await (await self._held()).write(data)

    @override
    def is_readable(self) -> bool:
        """Tell whether bytes can be read: they can, once anything has been read."""
        return True

    @override
    async def read(self, length: int) -> bytes:
        """Read up to ``length`` bytes, materialising the body if nothing has read it yet.

        Raises:
            StreamError: When the buffer cannot be read.
        """
        return await (await self._held()).read(length)

    @override
    async def get_contents(self) -> bytes:
        """Return every byte of the body, materialising it if nothing has read it yet.

        Raises:
            StreamError: When the buffer cannot be read.
        """
        return await (await self._held()).get_contents()

    @override
    def get_metadata(self, key: str | None = None) -> object:
        """Return what the buffer knows about itself, or nothing while there is none."""
        return (
            self._buffered.get_metadata(key)
            if self._buffered is not None
            else ({} if key is None else None)
        )
