from __future__ import annotations

from xtr_http_client_contracts import ChunkInterface

from xtr_http_client.chunk import InformationalChunk


def test_it_is_a_chunk() -> None:
    chunk: ChunkInterface = InformationalChunk(103, {})
    assert isinstance(chunk, ChunkInterface)


def test_it_reports_the_status_and_the_headers_it_came_with() -> None:
    chunk = InformationalChunk(103, {"link": ["</style.css>; rel=preload"]})
    assert chunk.get_informational_status() == (103, {"link": ["</style.css>; rel=preload"]})


def test_it_carries_no_body() -> None:
    chunk = InformationalChunk(100, {})
    assert chunk.get_content() == b""
    assert chunk.get_offset() == 0
    assert chunk.is_first() is False
    assert chunk.is_last() is False
    assert chunk.is_timeout() is False
    assert chunk.get_error() is None
