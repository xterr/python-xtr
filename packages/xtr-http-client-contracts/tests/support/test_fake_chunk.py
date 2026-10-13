from __future__ import annotations

from tests.support.fake_chunk import FakeChunk
from xtr_http_client_contracts import ChunkInterface


def test_it_is_a_chunk() -> None:
    assert isinstance(FakeChunk(), ChunkInterface)


def test_a_body_chunk_carries_its_content_and_where_it_sits() -> None:
    chunk = FakeChunk(b"body", offset=12)

    assert chunk.get_content() == b"body"
    assert chunk.get_offset() == 12
    assert not chunk.is_first()
    assert not chunk.is_last()
    assert not chunk.is_timeout()
    assert chunk.get_informational_status() is None
    assert chunk.get_error() is None


def test_the_chunks_that_mark_a_transfer_carry_no_content() -> None:
    assert FakeChunk(first=True).get_content() == b""
    assert FakeChunk(last=True).get_content() == b""
    assert FakeChunk(timeout=True).get_content() == b""


def test_an_informational_chunk_reports_the_status_and_headers_that_arrived() -> None:
    chunk = FakeChunk(informational=(103, {"link": ("</style.css>; rel=preload",)}))

    assert chunk.get_informational_status() == (103, {"link": ("</style.css>; rel=preload",)})


def test_a_failed_chunk_describes_what_went_wrong() -> None:
    assert FakeChunk(error="Connection reset by peer.").get_error() == "Connection reset by peer."
