from __future__ import annotations

from typing import TYPE_CHECKING, Self, final

import pytest
from xtr_http_client_contracts import ResponseStreamInterface

from tests.support.fake_response import FakeResponse
from xtr_http_client.chunk import FirstChunk, LastChunk
from xtr_http_client.response import ResponseStream

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from xtr_http_client_contracts import ChunkInterface, ResponseInterface

pytestmark = pytest.mark.anyio


async def _pairs(
    pairs: list[tuple[ResponseInterface, ChunkInterface]],
) -> AsyncIterator[tuple[ResponseInterface, ChunkInterface]]:
    for pair in pairs:
        yield pair


@final
class FailingPairs:
    """A transfer that breaks before it hands over anything."""

    def __aiter__(self) -> Self:
        return self

    async def __anext__(self) -> tuple[ResponseInterface, ChunkInterface]:
        raise OSError("Connection reset by peer")


def test_it_is_a_response_stream() -> None:
    stream: ResponseStreamInterface = ResponseStream(_pairs([]))
    assert isinstance(stream, ResponseStreamInterface)


async def test_it_yields_the_pairs_it_was_given_in_order() -> None:
    first = FakeResponse()
    second = FakeResponse()
    stream = ResponseStream(_pairs([(first, FirstChunk()), (second, LastChunk())]))

    seen = [pair async for pair in stream]

    assert len(seen) == 2
    assert seen[0][0] is first
    assert seen[0][1].is_first() is True
    assert seen[1][0] is second
    assert seen[1][1].is_last() is True


async def test_it_is_its_own_iterator() -> None:
    stream = ResponseStream(_pairs([(FakeResponse(), FirstChunk())]))

    assert aiter(stream) is stream


async def test_it_ends_once_nothing_is_left() -> None:
    stream = ResponseStream(_pairs([]))

    with pytest.raises(StopAsyncIteration):
        _ = await anext(stream)


async def test_what_the_transfer_raises_reaches_the_reader() -> None:
    stream = ResponseStream(FailingPairs())

    with pytest.raises(OSError, match="Connection reset by peer"):
        _ = await anext(stream)
