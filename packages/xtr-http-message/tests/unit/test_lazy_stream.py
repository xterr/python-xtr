"""Tests for :class:`xtr_http_message.lazy_stream.LazyStream`."""

from __future__ import annotations

from typing import final

import pytest

from xtr_http_message import LazyStream

pytestmark = pytest.mark.anyio


@final
class _Materialising:
    """A body a test reads through: what it yields, and how many times it was read."""

    __slots__ = ("body", "calls")

    def __init__(self, body: bytes) -> None:
        self.body = body
        self.calls = 0

    async def __call__(self) -> bytes:
        self.calls += 1
        return self.body


def test_nothing_is_read_until_something_reads_the_stream() -> None:
    read = _Materialising(b"four words")
    stream = LazyStream(read)

    assert (stream.materialised, read.calls) == (False, 0)


async def test_the_first_read_materialises_the_whole_body_once() -> None:
    read = _Materialising(b"four words")
    stream = LazyStream(read)

    assert await stream.get_contents() == b"four words"

    assert (stream.materialised, read.calls) == (True, 1)


async def test_every_later_read_is_served_out_of_the_buffer() -> None:
    read = _Materialising(b"four words")
    stream = LazyStream(read)

    assert await stream.get_contents() == b"four words"
    assert await stream.get_contents() == b"four words"
    _ = await stream.read(4)
    assert await stream.get_contents() == b"four words"

    assert read.calls == 1


async def test_a_partial_read_materialises_the_body() -> None:
    read = _Materialising(b"four words")
    stream = LazyStream(read)

    assert await stream.read(4) == b"four"

    assert (stream.materialised, read.calls) == (True, 1)
    assert await stream.read(4) == b" wor"


async def test_the_stream_is_seekable_and_rewindable() -> None:
    stream = LazyStream(_Materialising(b"four words"))

    assert stream.is_seekable() is True
    _ = await stream.read(4)
    await stream.rewind()
    assert await stream.read(4) == b"four"
    await stream.seek(5)
    assert await stream.read(5) == b"words"


async def test_closing_before_the_first_read_is_a_no_op() -> None:
    read = _Materialising(b"four words")
    stream = LazyStream(read)

    await stream.close()

    assert (stream.materialised, read.calls) == (False, 0)
    # The next reader still gets the bytes.
    assert await stream.get_contents() == b"four words"


def test_an_unread_stream_answers_for_the_buffer_it_will_be() -> None:
    stream = LazyStream(_Materialising(b"four words"))

    assert (stream.get_size(), stream.tell(), stream.eof()) == (None, 0, False)
    assert (stream.is_readable(), stream.is_writable()) == (True, True)
    assert stream.detach() is None
    assert (stream.get_metadata(), stream.get_metadata("uri")) == ({}, None)


async def test_a_materialised_stream_answers_what_the_buffer_knows() -> None:
    stream = LazyStream(_Materialising(b"four"))

    assert await stream.read(4) == b"four"

    assert stream.get_size() == 4
