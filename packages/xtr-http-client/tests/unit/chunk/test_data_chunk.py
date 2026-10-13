from __future__ import annotations

from xtr_http_client_contracts import ChunkInterface

from xtr_http_client.chunk import DataChunk


def test_it_is_a_chunk() -> None:
    chunk: ChunkInterface = DataChunk()
    assert isinstance(chunk, ChunkInterface)


def test_it_carries_the_content_it_was_given() -> None:
    assert DataChunk(0, b"hello").get_content() == b"hello"


def test_it_carries_the_offset_it_was_given() -> None:
    assert DataChunk(12, b"hello").get_offset() == 12


def test_it_is_empty_at_the_start_of_the_body_by_default() -> None:
    chunk = DataChunk()
    assert chunk.get_content() == b""
    assert chunk.get_offset() == 0


def test_it_reports_no_event_and_no_error() -> None:
    chunk = DataChunk(0, b"hello")
    assert chunk.is_timeout() is False
    assert chunk.is_first() is False
    assert chunk.is_last() is False
    assert chunk.get_informational_status() is None
    assert chunk.get_error() is None
