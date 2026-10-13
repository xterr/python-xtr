"""A message body read as the transfer produces it."""

from __future__ import annotations

import os
from tempfile import SpooledTemporaryFile
from typing import TYPE_CHECKING, Final, Protocol, cast, final, runtime_checkable

from xtr_http_message import Stream

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from typing import BinaryIO

    from xtr_http_message_contracts import StreamInterface

__all__ = ["ResponseBody"]

_READ_SIZE: Final = 65536

# Where a body stops being held in memory and starts being held in a file:
# enough that an ordinary response never reaches the disk, little enough that
# a download nobody sized cannot exhaust what is left of memory.
_SPILL_AT: Final = 2 * 1024 * 1024


@runtime_checkable
class _ClosableInterface(Protocol):
    """A source with something of its own to let go of."""

    async def aclose(self) -> None:
        """Let go of whatever the source was holding open."""
        ...


@final
class ResponseBody:
    """The body of a response, taken off the transfer as it is asked for.

    A message body is a cursor over bytes; a body still arriving has no bytes
    to be a cursor over yet. So a read that finds nothing waiting takes the
    next piece from the transfer, one piece at a time, until bytes turn up or
    the transfer is over — which the source says by ending. Nothing is fetched
    that nobody asked for, which is what makes a body the caller never reads
    cost nothing.

    Everything that arrives is written into a stream of its own, so the body
    can be read again — and is then seekable, once complete, because only then
    is there a whole body to seek in. That stream holds the first two
    mebibytes in memory and spills the rest to a file, so a large download is
    re-readable without being resident.

    Writing is not part of it: the bytes come from the far end.
    """

    __slots__ = ("_closed", "_complete", "_kept", "_received", "_source")

    def __init__(self, source: AsyncIterator[bytes]) -> None:
        """Hold onto the transfer this body comes out of.

        Args:
            source: The pieces of the body, in the order they arrive. Ending
                is how it says the transfer is complete. Whatever else it
                raises is left alone: what a broken transfer means for a
                response is the response's to decide, not the body's.
        """
        self._source = source
        self._kept: StreamInterface | None = None
        self._received = 0
        self._complete = False
        self._closed = False

    @property
    def complete(self) -> bool:
        """Whether the whole body has arrived."""
        return self._complete

    @property
    def received(self) -> int:
        """How many bytes have arrived so far."""
        return self._received

    async def close(self) -> None:
        """Let go of the body, the transfer behind it, and what it was kept in.

        Nothing can be read from it afterwards.
        """
        self._closed = True

        if isinstance(self._source, _ClosableInterface):
            await self._source.aclose()

        if self._kept is not None:
            await self._kept.close()

    def detach(self) -> BinaryIO | None:
        """Return nothing: what a body is kept in is its own, not a caller's to take over."""
        return None

    def get_size(self) -> int | None:
        """Return the size of the body, which is known once it is complete."""
        if not self._complete:
            return None
        if self._kept is None:
            return self._received
        return self._kept.get_size()

    def tell(self) -> int:
        """Return how far into the body reading has got."""
        if self._kept is None:
            return 0
        return self._kept.tell()

    def eof(self) -> bool:
        """Tell whether reading has reached the end of a body that has all arrived."""
        return self._complete and self.tell() >= self._received

    def is_seekable(self) -> bool:
        """Tell whether the cursor can be moved.

        Only once the whole body has arrived: before that there is no whole
        body to move about in.
        """
        return not self._closed and self._complete

    async def seek(self, offset: int, whence: int = os.SEEK_SET) -> None:
        """Move the cursor to a position in the body.

        Raises:
            ValueError: When ``whence`` is not one of the three the standard
                library defines.
            RuntimeError: When this body cannot be seeked in, or the position
                asked for is before its first byte.
        """
        if not self.is_seekable():
            raise RuntimeError(
                "The response body cannot be rewound: it is read as the transfer produces it."
            )

        origins = {os.SEEK_SET: 0, os.SEEK_CUR: self.tell(), os.SEEK_END: self._received}
        if whence not in origins:
            raise ValueError(f"Invalid whence: {whence}.")

        target = origins[whence] + offset
        if target < 0:
            raise RuntimeError(f"Cannot seek to {target}: that is before the body starts.")

        if self._kept is not None:
            await self._kept.seek(target)

    async def rewind(self) -> None:
        """Move the cursor back to the first byte of the body.

        Raises:
            RuntimeError: When this body cannot be seeked in.
        """
        await self.seek(0)

    def is_writable(self) -> bool:
        """Say no: the bytes of a response come from the far end."""
        return False

    async def write(self, data: bytes) -> int:
        """Refuse to write.

        Raises:
            RuntimeError: Always.
        """
        del data
        raise RuntimeError("A response body cannot be written to.")

    def is_readable(self) -> bool:
        """Tell whether the body can still be read."""
        return not self._closed

    async def read(self, length: int) -> bytes:
        """Read up to ``length`` bytes from the cursor.

        Takes pieces off the transfer until bytes turn up past the cursor or
        the transfer is over, then hands over what is there — which may be
        less than was asked for, because a transfer arrives in pieces and
        waiting for the rest would hold up a reader that has something to do
        with this piece.

        Returns:
            What was read, or empty bytes once the body is exhausted.

        Raises:
            RuntimeError: When the body has been closed.
        """
        if self._closed:
            raise RuntimeError("The response body is closed.")
        if length <= 0:
            return b""

        while self._waiting() == 0 and not self._complete:
            await self._receive()

        if self._kept is None:
            return b""
        return await self._kept.read(length)

    async def get_contents(self) -> bytes:
        """Read the whole of the body, rewinding first when that is possible.

        Returns:
            Every byte left in the body.

        Raises:
            RuntimeError: When the body has been closed.
        """
        if self.is_seekable():
            await self.rewind()

        pieces: list[bytes] = []
        while True:
            piece = await self.read(_READ_SIZE)
            if not piece:
                return b"".join(pieces)
            pieces.append(piece)

    def get_metadata(self, key: str | None = None) -> object:
        """Return what this body knows about itself, or one entry of it."""
        metadata: dict[str, object] = {
            "mode": "rb",
            "seekable": self.is_seekable(),
            "eof": self.eof(),
        }
        if key is None:
            return metadata
        return metadata.get(key)

    async def _receive(self) -> None:
        """Take the next piece off the transfer, or learn that there is none."""
        try:
            piece = await anext(self._source)
        except StopAsyncIteration:
            self._complete = True
            return
        await self._arrived(piece)

    async def _arrived(self, piece: bytes) -> None:
        """Count a piece in, and keep it where a reader can still reach it."""
        self._received += len(piece)

        # The kept stream's cursor *is* the read cursor, so an arriving piece
        # is appended at the end and the cursor put back where the reader left
        # it.
        kept = self._keep()
        reading_at = kept.tell()
        await kept.seek(0, os.SEEK_END)
        _ = await kept.write(piece)
        await kept.seek(reading_at)

    def _keep(self) -> StreamInterface:
        """Return the stream the body is held in, opening it on first use."""
        if self._kept is None:
            # Held open past this call on purpose: `close` is what lets go of
            # it. And it is a binary file object in every way a stream uses
            # one — only typed as the wider `IO[bytes]`, whose `write` takes
            # the narrower `bytes` a body ever passes.
            spooled = SpooledTemporaryFile(max_size=_SPILL_AT)  # noqa: SIM115
            self._kept = Stream.create(cast("BinaryIO", cast("object", spooled)))
        return self._kept

    def _waiting(self) -> int:
        """How many bytes have arrived that the cursor has not reached."""
        if self._kept is None:
            return 0
        return max(0, self._received - self._kept.tell())
