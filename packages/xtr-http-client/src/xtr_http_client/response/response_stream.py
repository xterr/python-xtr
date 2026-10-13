"""Several transfers read as one run of chunks."""

from __future__ import annotations

from typing import TYPE_CHECKING, Self, final

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from xtr_http_client_contracts import ChunkInterface, ResponseInterface

__all__ = ["ResponseStream"]


@final
class ResponseStream:
    """Chunks from any number of responses, each paired with the one it is from.

    What a client hands back from ``stream()``. The interleaving — pulling
    from every response at once so a slow transfer never holds up a fast one
    — is the client's, written as an async iterator over pairs; this is the
    seam that gives it the shape the contract asks for, an iterator that is
    also its own iterable, so ``async for`` works on it directly.

    Keeping the two apart is what lets the same wrapper go over any such
    iterator: a client multiplexing real connections, a mock client replaying
    a script, or a decorator that filters what another stream yielded.
    """

    __slots__ = ("_pairs",)

    def __init__(self, pairs: AsyncIterator[tuple[ResponseInterface, ChunkInterface]]) -> None:
        """Wrap the run of pairs a client produced."""
        self._pairs = pairs

    def __aiter__(self) -> Self:
        """Return this stream, which is its own iterator."""
        return self

    async def __anext__(self) -> tuple[ResponseInterface, ChunkInterface]:
        """Return the next pair, once there is one.

        Returns:
            The response a chunk arrived for, and the chunk.

        Raises:
            StopAsyncIteration: Once every response has finished.
        """
        return await anext(self._pairs)
