"""A message body held in memory, standing in for one coming off a transfer."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, final

if TYPE_CHECKING:
    from typing import BinaryIO

__all__ = ["FakeStream"]


@final
class FakeStream:
    """A cursor over bytes kept in memory.

    Enough of a body for the contract's shapes to be exercised without a
    socket: the client response hands one of these out of ``get_body()``, and
    closing it is what proves ``cancel()`` and leaving ``async with`` let go of
    the transfer.
    """

    def __init__(self, data: bytes = b"") -> None:
        self._buffer = bytearray(data)
        self._position = 0
        self._closed = False

    @property
    def closed(self) -> bool:
        """Tell whether the stream has been closed."""
        return self._closed

    async def close(self) -> None:
        self._closed = True

    def detach(self) -> BinaryIO | None:
        self._closed = True
        return None

    def get_size(self) -> int | None:
        return len(self._buffer)

    def tell(self) -> int:
        return self._position

    def eof(self) -> bool:
        return self._position >= len(self._buffer)

    def is_seekable(self) -> bool:
        return not self._closed

    async def seek(self, offset: int, whence: int = os.SEEK_SET) -> None:
        if self._closed:
            raise RuntimeError("The stream is closed.")
        origin = {
            os.SEEK_SET: 0,
            os.SEEK_CUR: self._position,
            os.SEEK_END: len(self._buffer),
        }[whence]
        self._position = max(0, origin + offset)

    async def rewind(self) -> None:
        await self.seek(0)

    def is_writable(self) -> bool:
        return not self._closed

    async def write(self, data: bytes) -> int:
        if self._closed:
            raise RuntimeError("The stream is closed.")
        self._buffer[self._position : self._position + len(data)] = data
        self._position += len(data)
        return len(data)

    def is_readable(self) -> bool:
        return not self._closed

    async def read(self, length: int) -> bytes:
        if self._closed:
            raise RuntimeError("The stream is closed.")
        chunk = bytes(self._buffer[self._position : self._position + length])
        self._position += len(chunk)
        return chunk

    async def get_contents(self) -> bytes:
        await self.rewind()
        return await self.read(len(self._buffer))

    def get_metadata(self, key: str | None = None) -> object:
        metadata: dict[str, object] = {"mode": "rb+", "seekable": self.is_seekable()}
        if key is None:
            return metadata
        return metadata.get(key)
