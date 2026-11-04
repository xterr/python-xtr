"""A message already rendered: bytes handed over as they are."""

from __future__ import annotations

from collections.abc import Generator, Iterator
from typing import TYPE_CHECKING, BinaryIO, Final, Protocol, final, runtime_checkable

from .exception import InvalidArgumentError, LogicError

if TYPE_CHECKING:
    from collections.abc import Iterable

__all__ = ["RawMessage"]

_CLOSED: Final = "Unable to send the email as its generator is already closed."


@runtime_checkable
class _BinaryFile(Protocol):
    """A binary file, read line by line from its start."""

    def seekable(self) -> bool: ...

    def seek(self, offset: int, whence: int = 0, /) -> int: ...

    def readline(self, size: int = -1, /) -> bytes: ...


class RawMessage:
    """A message sent as the bytes it already is, nothing parsed or added.

    The content is a string (sent as UTF-8), bytes, a binary file (read from its start, line
    by line, each time it is sent; whoever opened it closes it) or chunks of bytes. An iterator
    of chunks — a generator — can be read once: what it yields is kept as it goes, so a
    message read to its end can be sent again, and one left half read cannot.

    A copy reads the same iterator as the message it copies: the bytes one of them read to the
    end are there for every other, and a read one of them left half done — or is still doing —
    leaves every other unable to read.

    A string may carry bytes that are not UTF-8 as the surrogates :meth:`to_string` gives them
    as; any other lone surrogate has no bytes to be sent as, and the message is refused.
    """

    def __init__(self, message: str | bytes | BinaryIO | Iterable[bytes]) -> None:
        """Keep ``message``; nothing is read until the message is."""
        self._message: str | bytes | BinaryIO | Iterable[bytes] | _ReadOnce = (
            _ReadOnce(message)
            if isinstance(message, Iterator) and not isinstance(message, _BinaryFile)
            else message
        )

    def to_string(self) -> str:
        """Return the whole message as text; bytes that are not UTF-8 survive as surrogates.

        A string is checked as sending it would be: what this returns is the text of what is
        sent, and a string that cannot be sent has none.

        Raises:
            LogicError: The message is a generator that was left half read.
            InvalidArgumentError: The message is a string UTF-8 cannot hold.
        """
        if isinstance(self._message, str):
            _ = _encoded(self._message)
            return self._message
        return b"".join(self.to_iterable()).decode("utf-8", "surrogateescape")

    def to_iterable(self) -> Generator[bytes, None, None]:
        """Yield the message in the pieces it is held in, as a mail server receives them.

        Closing the generator before its end leaves a message held as a generator unreadable.

        Raises:
            LogicError: The message is a generator that was left half read.
            InvalidArgumentError: The message is a string UTF-8 cannot hold.
        """
        message = self._message
        if isinstance(message, str):
            yield _encoded(message)
        elif isinstance(message, bytes):
            yield message
        elif isinstance(message, _BinaryFile):
            if message.seekable():
                _ = message.seek(0)
            yield from iter(message.readline, b"")
        elif isinstance(message, _ReadOnce):
            yield from message.read()
        else:
            yield from message

    def ensure_validity(self) -> None:
        """Check the message can be sent; a raw message always can.

        Raises:
            LogicError: In a subclass, the message cannot be sent as it is.
        """


@final
class _ReadOnce:
    """Chunks that can be read once, held by a message and every copy of it.

    The first read takes the chunks; once it reaches their end, the bytes it read are what
    every later read yields. Until then — and for good, when it stops half way — there is
    nothing left to read.
    """

    __slots__ = ("_chunks", "_content")

    def __init__(self, chunks: Iterator[bytes]) -> None:
        self._chunks: Iterator[bytes] | None = chunks
        self._content: bytes | None = None

    def read(self) -> Generator[bytes, None, None]:
        if self._content is not None:
            yield self._content
            return
        chunks = self._chunks
        if chunks is None:
            raise LogicError(_CLOSED)
        self._chunks = None
        read: list[bytes] = []
        for chunk in chunks:
            read.append(chunk)
            yield chunk
        self._content = b"".join(read)


def _encoded(message: str) -> bytes:
    try:
        return message.encode("utf-8", "surrogateescape")
    except UnicodeEncodeError as error:
        # The codec's message shows the character escaped.
        raise InvalidArgumentError(f"The message cannot be written in UTF-8: {error}.") from error
