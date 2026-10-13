"""One response's chunks, from the backend receiving them to whoever reads them."""

from __future__ import annotations

from collections import deque
from contextlib import ExitStack, contextmanager
from typing import TYPE_CHECKING, Final, final

import anyio

from xtr_http_client.chunk.error_chunk import ErrorChunk
from xtr_http_client.exception import TransportError

if TYPE_CHECKING:
    from collections.abc import Callable, Generator, Sequence

    from xtr_http_client_contracts import ChunkInterface

__all__ = ["Transfer"]


@final
class Transfer:
    """The single source of one response's chunks.

    A backend pushes what arrives — pieces of the body, 1xx statuses, the end,
    or what broke it — and readers take it: the response's body as it is read,
    and any ``stream()`` run the response is in. Each chunk goes to exactly one
    of them, so a byte read off the network is read once whoever asks for it;
    a run hands what it took to the body itself.

    A transfer that is over stays over. Once its last chunk, or the failure
    that ended it, has been taken, every later take returns that chunk again,
    so a reader coming back learns how it ended instead of waiting for a chunk
    that will never come.

    Nothing here keeps time: a reader says how long it waits. That is what lets
    a run wait on several transfers at once without a task for each.
    """

    CANCELED: Final = "Response has been canceled."

    __slots__ = (
        "_canceled",
        "_chunks",
        "_closed",
        "_end",
        "_error",
        "_listeners",
        "_offset",
        "_timeout",
        "on_cancel",
    )

    def __init__(self, timeout: float) -> None:
        """Start a transfer that has received nothing yet.

        Args:
            timeout: How long a reader waits for the next chunk before it
                reports the transfer as idle, in seconds.
        """
        self._timeout = timeout
        self._chunks: deque[ChunkInterface] = deque()
        self._listeners: set[anyio.Event] = set()
        self._end: ChunkInterface | None = None
        self._error: str | None = None
        self._offset = 0
        self._closed = False
        self._canceled = False
        self.on_cancel: Callable[[], None] | None = None
        """What stops the producer; the backend sets it when it starts one."""

    @property
    def timeout(self) -> float:
        """How long a reader waits for the next chunk, in seconds."""
        return self._timeout

    @property
    def offset(self) -> int:
        """Where the body pushed so far ends, which is where the next piece starts."""
        return self._offset

    @property
    def error(self) -> str | None:
        """What broke the transfer, once something has; a cancel is not a failure."""
        return self._error

    @property
    def canceled(self) -> bool:
        """Whether the transfer was abandoned before its end was taken."""
        return self._canceled

    @property
    def finished(self) -> bool:
        """Whether its end has been taken, so nothing new will come out of it."""
        return self._end is not None

    def push(self, chunk: ChunkInterface) -> None:
        """Hand over a chunk that arrived, waking whoever waits on this transfer.

        Ignored once the transfer has ended or been canceled, so a producer
        racing a cancel cannot add to a transfer nobody reads any more.
        """
        if self._closed:
            return
        if chunk.get_error() is None:
            self._offset = max(self._offset, chunk.get_offset() + len(chunk.get_content()))
        elif not chunk.is_timeout():
            self._error = chunk.get_error()
        self._closed = _ends(chunk)
        self._chunks.append(chunk)
        self._wake()

    def fail(self, error: BaseException) -> None:
        """End the transfer with the error that broke it."""
        self.push(ErrorChunk(self._offset, error))

    def take_ready(self) -> ChunkInterface | None:
        """Take the next chunk if one is there, without waiting for it.

        Returns:
            The next chunk; the one the transfer ended with, once it is over;
            ``None`` while nothing has arrived.
        """
        if not self._chunks:
            return self._end
        chunk = self._chunks.popleft()
        if _ends(chunk):
            self._end = chunk
        return chunk

    async def next_chunk(self) -> ChunkInterface:
        """Take the next chunk, waiting for as long as it takes to arrive."""
        while (chunk := self.take_ready()) is None:
            await Transfer.wait_any((self,))
        return chunk

    def idle_chunk(self, url: object, after: float) -> ErrorChunk:
        """Say that nothing came in for ``after`` seconds, and where the body had got to."""
        return ErrorChunk(self._offset, f'Idle timeout reached for "{url}".', after)

    def cancel(self) -> None:
        """Abandon the transfer: stop its producer and drop what nobody took.

        Ends the transfer with "Response has been canceled.", which is what a
        reader still waiting on it is handed. A transfer whose end was already
        taken is left as it is, and a producer that already ended is not
        stopped again.
        """
        if self._end is not None:
            return
        producing = not self._closed
        self._chunks.clear()
        self._end = ErrorChunk(self._offset, TransportError(self.CANCELED))
        self._closed = True
        self._canceled = True
        self._wake()
        if producing and self.on_cancel is not None:
            self.on_cancel()

    @property
    def ready(self) -> bool:
        """Whether a take would hand over a chunk without waiting."""
        return bool(self._chunks) or self._end is not None

    @contextmanager
    def waking(self, event: anyio.Event) -> Generator[None, None, None]:
        """Set ``event`` whenever a chunk is pushed, for as long as the block lasts."""
        self._listeners.add(event)
        try:
            yield
        finally:
            self._listeners.discard(event)

    @staticmethod
    async def wait_any(transfers: Sequence[Transfer]) -> None:
        """Wait until any of ``transfers`` has a chunk to take.

        One event is shared by all of them, set by whichever is pushed to
        first, so waiting on any number of transfers takes no task of its own;
        how long to wait is the caller's cancel scope.
        """
        if any(transfer.ready for transfer in transfers):
            return
        event = anyio.Event()
        with ExitStack() as listening:
            for transfer in transfers:
                listening.enter_context(transfer.waking(event))
            await event.wait()

    def _wake(self) -> None:
        for listener in self._listeners:
            listener.set()


def _ends(chunk: ChunkInterface) -> bool:
    """Tell whether nothing comes after ``chunk``: it is the last one, or a failure."""
    if chunk.get_error() is None:
        return chunk.is_last()
    return not chunk.is_timeout()
