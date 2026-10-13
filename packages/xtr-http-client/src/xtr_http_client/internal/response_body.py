"""A message body read as the transfer produces it."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Final, final

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from typing import BinaryIO

__all__ = ["ResponseBody"]

_READ_SIZE: Final = 65536


@final
class ResponseBody:
    """The body of a response, pulled out of the transfer as it is asked for.

    A message body is a cursor over bytes; a body still arriving has no bytes
    to be a cursor over yet. So this holds no data of its own: a read that
    finds the window empty drives the transfer a step at a time until bytes
    turn up past the cursor or there is nothing more coming. Nothing is
    fetched that nobody asked for, which is what makes a body the caller never
    reads cost nothing.

    Whether the bytes are *kept* is the other half. A body being kept holds
    everything that arrived, so it can be read again — and is then seekable,
    once complete, because only then is there a whole body to seek in. A body
    not being kept drops what has been consumed, so a large download costs one
    window rather than all of it, and reading it twice gives nothing the
    second time.

    Writing is not part of it: the bytes come from the far end.
    """

    __slots__ = (
        "_buffered",
        "_closed",
        "_complete",
        "_cursor",
        "_pull",
        "_received",
        "_window",
        "_window_start",
    )

    def __init__(self, pull: Callable[[], Awaitable[bool]], buffered: bool) -> None:
        """Hold onto the transfer this body comes out of.

        Args:
            pull: Drives the transfer one step. Returns ``False`` once nothing
                more can arrive, so a read knows to stop asking. Whatever it
                raises is left alone: what a broken transfer means for a
                response is the response's to decide, not the body's.
            buffered: Whether to keep what arrived for a second read.
        """
        self._pull = pull
        self._buffered = buffered
        self._window = b""
        self._window_start = 0
        self._cursor = 0
        self._received = 0
        self._complete = False
        self._closed = False

    @property
    def buffered(self) -> bool:
        """Whether what arrived is being kept for a second read."""
        return self._buffered

    @property
    def complete(self) -> bool:
        """Whether the whole body has arrived."""
        return self._complete

    @property
    def received(self) -> int:
        """How many bytes have arrived so far."""
        return self._received

    def append(self, data: bytes) -> None:
        """Add bytes that just arrived to the end of the body."""
        self._window += data
        self._received += len(data)

    def finish(self) -> None:
        """Mark the body complete, with nothing further to arrive.

        A body that never received anything becomes kept, whatever was asked
        for: there is nothing to hold, and an empty body that could only be
        read once would make "read twice" fail for the one case where the
        answer is not in doubt.
        """
        self._complete = True
        if self._received == 0:
            self._buffered = True

    async def close(self) -> None:
        """Let go of the body; nothing can be read from it afterwards."""
        self._closed = True

    def detach(self) -> BinaryIO | None:
        """Return nothing: a body off a transfer wraps no file object."""
        return None

    def get_size(self) -> int | None:
        """Return the size of the body, which is known once it is complete and kept."""
        if self._complete and self._buffered:
            return self._received
        return None

    def tell(self) -> int:
        """Return how far into the body the cursor has got."""
        return self._cursor

    def eof(self) -> bool:
        """Tell whether the cursor has reached the end of a body that has all arrived."""
        return self._complete and self._cursor >= self._received

    def is_seekable(self) -> bool:
        """Tell whether the cursor can be moved.

        Only a body that is kept and has all arrived: anything else has no
        whole body to move about in.
        """
        return not self._closed and self._buffered and self._complete

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

        origins = {os.SEEK_SET: 0, os.SEEK_CUR: self._cursor, os.SEEK_END: self._received}
        if whence not in origins:
            raise ValueError(f"Invalid whence: {whence}.")

        target = origins[whence] + offset
        if target < 0:
            raise RuntimeError(f"Cannot seek to {target}: that is before the body starts.")

        self._cursor = target

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

        Drives the transfer until bytes turn up past the cursor or nothing
        more can arrive, then hands over what is there — which may be less
        than was asked for, because a transfer arrives in pieces and waiting
        for the rest would hold up a reader that has something to do with
        this piece.

        Returns:
            What was read, or empty bytes once the body is exhausted.

        Raises:
            RuntimeError: When the body has been closed.
        """
        if self._closed:
            raise RuntimeError("The response body is closed.")
        if length <= 0:
            return b""

        while self._available() == 0 and not self._complete:
            if not await self._pull():
                break

        start = self._cursor - self._window_start
        data = self._window[start : start + length]
        self._cursor += len(data)

        if not self._buffered:
            self._window = self._window[start + len(data) :]
            self._window_start = self._cursor

        return data

    async def get_contents(self) -> bytes:
        """Read the whole of the body, rewinding first when that is possible.

        On a body that cannot be rewound this reads from wherever the cursor
        sits, so a second call gives nothing: the bytes were handed over once
        and not kept.

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

    def _available(self) -> int:
        """How many bytes sit in the window past the cursor."""
        return max(0, len(self._window) - (self._cursor - self._window_start))
