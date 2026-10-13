from __future__ import annotations

from xtr_http_client_contracts import ChunkInterface

from xtr_http_client.chunk import LastChunk


def test_it_is_a_chunk() -> None:
    chunk: ChunkInterface = LastChunk()
    assert isinstance(chunk, ChunkInterface)


def test_it_reports_the_body_is_complete() -> None:
    assert LastChunk().is_last() is True


def test_it_still_carries_the_offset_the_body_ended_at() -> None:
    chunk = LastChunk(42)
    assert chunk.get_offset() == 42
    assert chunk.get_content() == b""
    assert chunk.is_first() is False
