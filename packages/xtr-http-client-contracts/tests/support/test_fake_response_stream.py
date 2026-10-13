from __future__ import annotations

import pytest

from tests.support.fake_chunk import FakeChunk
from tests.support.fake_response import FakeResponse
from tests.support.fake_response_stream import FakeResponseStream
from xtr_http_client_contracts import ResponseStreamInterface

pytestmark = pytest.mark.anyio


def test_it_is_a_response_stream() -> None:
    assert isinstance(FakeResponseStream([]), ResponseStreamInterface)


async def test_it_yields_each_pair_once_in_order() -> None:
    response = FakeResponse()
    first = FakeChunk(first=True)
    body = FakeChunk(b"hello")
    stream = FakeResponseStream([(response, first), (response, body)])

    seen = [(answered, chunk) async for answered, chunk in stream]

    assert seen == [(response, first), (response, body)]


async def test_an_empty_run_ends_straight_away() -> None:
    assert [pair async for pair in FakeResponseStream([])] == []
