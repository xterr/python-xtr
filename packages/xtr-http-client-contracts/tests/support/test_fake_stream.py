from __future__ import annotations

import pytest
from xtr_http_message_contracts import StreamInterface

from tests.support.fake_stream import FakeStream

pytestmark = pytest.mark.anyio


def test_it_is_a_message_body() -> None:
    assert isinstance(FakeStream(), StreamInterface)


async def test_reading_takes_from_the_cursor_and_moves_it() -> None:
    stream = FakeStream(b"hello world")

    assert await stream.read(5) == b"hello"
    assert stream.tell() == 5
    assert not stream.eof()


async def test_the_contents_come_back_whole_however_far_the_cursor_moved() -> None:
    stream = FakeStream(b"hello")
    _ = await stream.read(3)

    assert await stream.get_contents() == b"hello"
    assert stream.eof()


async def test_writing_puts_bytes_at_the_cursor() -> None:
    stream = FakeStream()

    assert await stream.write(b"body") == 4
    assert await stream.get_contents() == b"body"


async def test_seeking_from_the_end_counts_backwards() -> None:
    stream = FakeStream(b"hello")

    await stream.seek(-2, 2)

    assert await stream.read(2) == b"lo"


async def test_a_closed_stream_refuses_everything_it_was_asked_to_do() -> None:
    stream = FakeStream(b"hello")
    await stream.close()

    assert stream.closed
    assert not stream.is_readable()
    assert not stream.is_writable()
    assert not stream.is_seekable()
    with pytest.raises(RuntimeError):
        _ = await stream.read(1)
    with pytest.raises(RuntimeError):
        _ = await stream.write(b"x")
    with pytest.raises(RuntimeError):
        await stream.seek(0)


def test_detaching_hands_nothing_over_and_leaves_the_stream_closed() -> None:
    stream = FakeStream(b"hello")

    assert stream.detach() is None
    assert stream.closed


def test_the_metadata_reports_entry_by_entry_or_all_at_once() -> None:
    stream = FakeStream()

    assert stream.get_metadata("seekable") is True
    assert stream.get_metadata("absent") is None
    assert stream.get_metadata() == {"mode": "rb+", "seekable": True}


def test_the_size_is_the_number_of_bytes_held() -> None:
    assert FakeStream(b"hello").get_size() == 5
