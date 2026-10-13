from __future__ import annotations

import io
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from tests.support.unreadable_file import UnreadableFile
from tests.support.unseekable_file import UnseekableFile
from xtr_http_message.exception import StreamError
from xtr_http_message.stream import Stream

if TYPE_CHECKING:
    from collections.abc import Iterator
    from typing import BinaryIO

pytestmark = pytest.mark.anyio


def _written(data: bytes) -> io.BytesIO:
    """Return a buffer holding ``data``, with the cursor left after it.

    The harness opens a buffer in memory and writes to it, which leaves the
    cursor at the end; a stream built over one therefore starts there.
    """
    buffer = io.BytesIO()
    _ = buffer.write(data)

    return buffer


@pytest.fixture
def read_only_file() -> Iterator[BinaryIO]:
    """Open this very file for reading, as the harness opens its own.

    The harness reaches for a remote URL for a stream that cannot be written
    to; a file opened for reading is one without the suite needing a network.
    """
    with Path(__file__).open("rb") as file:
        yield file


async def test_a_stream_that_cannot_be_written_to_still_reads_whole(
    read_only_file: BinaryIO,
) -> None:
    assert await Stream.create(read_only_file).get_contents() != b""


async def test_a_stream_is_rewound_before_it_is_read_whole() -> None:
    buffer = _written(b"abcdef")
    _ = buffer.seek(3)

    assert await Stream.create(buffer).get_contents() == b"abcdef"


async def test_closing_a_stream_closes_the_file_it_wraps() -> None:
    buffer = _written(b"abcdef")
    stream = Stream.create(buffer)

    assert buffer.closed is False
    await stream.close()
    assert buffer.closed is True


def test_detaching_a_stream_hands_back_the_file_it_wrapped() -> None:
    buffer = _written(b"abc")

    assert Stream.create(buffer).detach() is buffer


def test_the_size_is_the_number_of_bytes_written() -> None:
    assert Stream.create(_written(b"abc")).get_size() == 3


def test_the_cursor_sits_after_what_was_written() -> None:
    assert Stream.create(_written(b"abcdef")).tell() == 6


@pytest.mark.parametrize("offset", [0, 3, 6])
async def test_the_cursor_is_reported_where_it_was_moved_to(offset: int) -> None:
    stream = Stream.create(_written(b"abcdef"))

    await stream.seek(offset)

    assert stream.tell() == offset


async def test_the_end_is_reached_once_reading_has_run_out() -> None:
    stream = Stream.create(_written(b"abcdef"))
    await stream.seek(0)

    assert stream.eof() is False
    _ = await stream.read(20)
    _ = await stream.read(10)
    assert stream.eof() is True


def test_a_stream_over_a_buffer_can_be_seeked() -> None:
    assert Stream.create(_written(b"abcdef")).is_seekable() is True


def test_a_stream_over_a_file_that_does_not_seek_cannot_be_seeked() -> None:
    """The harness reaches for a remote URL; the fake stands in for one."""
    assert Stream.create(UnseekableFile(b"abcdef")).is_seekable() is False


def test_a_stream_over_a_buffer_can_be_written_to() -> None:
    assert Stream.create(_written(b"abcdef")).is_writable() is True


def test_a_stream_over_a_file_opened_for_reading_cannot_be_written_to(
    read_only_file: BinaryIO,
) -> None:
    assert Stream.create(read_only_file).is_writable() is False


def test_a_stream_over_a_buffer_can_be_read() -> None:
    assert Stream.create(_written(b"abcdef")).is_readable() is True


def test_a_stream_over_a_file_opened_for_reading_can_be_read(read_only_file: BinaryIO) -> None:
    assert Stream.create(read_only_file).is_readable() is True


def test_a_stream_that_cannot_be_read_reports_so() -> None:
    """Not a scenario of the harness, whose read-only subject does read.

    What it opens for its three read-only scenarios is a remote URL, which is
    readable; a stream that is not is the other half of the contract, and the
    fake is one without the suite needing a network.
    """
    assert Stream.create(UnreadableFile()).is_readable() is False


async def test_seeking_a_stream_moves_the_file_it_wraps() -> None:
    buffer = _written(b"abcdef")

    await Stream.create(buffer).seek(3)

    assert buffer.read(3) == b"def"


async def test_rewinding_a_stream_moves_the_file_it_wraps_back() -> None:
    buffer = _written(b"abcdef")

    await Stream.create(buffer).rewind()

    assert buffer.read(6) == b"abcdef"


async def test_a_stream_that_does_not_seek_cannot_be_rewound() -> None:
    """The harness reaches for a remote URL; the fake stands in for one."""
    with pytest.raises(StreamError):
        await Stream.create(UnseekableFile(b"abcdef")).rewind()


async def test_writing_reports_how_much_was_written() -> None:
    stream = Stream.create(_written(b"abc"))

    assert await stream.write(b"def") == 3
    assert await stream.get_contents() == b"abcdef"


async def test_reading_takes_what_is_asked_for_and_then_what_is_left() -> None:
    stream = Stream.create(_written(b"abcdef"))
    await stream.rewind()

    assert await stream.read(3) == b"abc"
    assert await stream.read(10) == b"def"


async def test_the_whole_of_a_stream_is_read_however_often_it_is_asked_for() -> None:
    stream = Stream.create(_written(b"abcdef"))
    await stream.seek(3)

    assert await stream.get_contents() == b"abcdef"
    assert await stream.get_contents() == b"abcdef"


async def test_reading_the_whole_of_a_stream_whose_file_was_closed_fails() -> None:
    buffer = _written(b"abcdef")
    _ = buffer.seek(0)
    stream = Stream.create(buffer)

    buffer.close()

    with pytest.raises(StreamError):
        _ = await stream.get_contents()
