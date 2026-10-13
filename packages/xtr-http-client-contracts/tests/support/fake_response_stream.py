"""A prepared run of chunks, standing in for what ``stream()`` hands back."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterable, Sequence

    from xtr_http_client_contracts import ChunkInterface, ResponseInterface

__all__ = ["FakeResponseStream"]


@final
class FakeResponseStream:
    """Yields the pairs it was built with, each once, in order."""

    def __init__(self, pairs: Iterable[tuple[ResponseInterface, ChunkInterface]]) -> None:
        self._pairs: Sequence[tuple[ResponseInterface, ChunkInterface]] = tuple(pairs)
        self._next = 0

    def __aiter__(self) -> AsyncIterator[tuple[ResponseInterface, ChunkInterface]]:
        return self

    async def __anext__(self) -> tuple[ResponseInterface, ChunkInterface]:
        if self._next >= len(self._pairs):
            raise StopAsyncIteration
        pair = self._pairs[self._next]
        self._next += 1
        return pair
