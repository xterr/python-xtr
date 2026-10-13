from __future__ import annotations

from collections.abc import AsyncIterator

from tests.support.fake_response_stream import FakeResponseStream
from xtr_http_client_contracts import ChunkInterface, ResponseInterface, ResponseStreamInterface


def test_a_stream_of_pairs_satisfies_it() -> None:
    stream: ResponseStreamInterface = FakeResponseStream([])

    assert isinstance(stream, ResponseStreamInterface)


def test_an_unrelated_object_does_not() -> None:
    assert not isinstance(object(), ResponseStreamInterface)


def test_a_response_stream_is_an_async_iterator_of_pairs() -> None:
    stream: ResponseStreamInterface = FakeResponseStream([])
    as_iterator: AsyncIterator[tuple[ResponseInterface, ChunkInterface]] = stream

    assert as_iterator is stream
    assert isinstance(stream, AsyncIterator)
