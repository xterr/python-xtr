from __future__ import annotations

from xtr_http_client_contracts import ChunkInterface

from xtr_http_client.chunk import FirstChunk


def test_it_is_a_chunk() -> None:
    chunk: ChunkInterface = FirstChunk()
    assert isinstance(chunk, ChunkInterface)


def test_it_reports_the_head_has_arrived() -> None:
    assert FirstChunk().is_first() is True


def test_it_is_otherwise_a_data_chunk() -> None:
    chunk = FirstChunk(0, b"body")
    assert chunk.get_content() == b"body"
    assert chunk.is_last() is False
    assert chunk.is_timeout() is False
    assert chunk.get_informational_status() is None
