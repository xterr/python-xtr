from __future__ import annotations

import io
import os
import re
from typing import TYPE_CHECKING, BinaryIO, Literal, cast

import pytest
from xtr_http_message_contracts import StreamInterface

from tests.support.broken_file import BrokenFile
from tests.support.unreadable_file import UnreadableFile
from tests.support.unseekable_file import UnseekableFile
from xtr_http_message.exception import StreamError
from xtr_http_message.stream import Stream

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Iterator
    from pathlib import Path

pytestmark = pytest.mark.anyio

_ONE_MIB = 1_048_576


def _file(
    tmp_path: Path,
    content: bytes = b"",
    mode: Literal["rb", "rb+", "wb"] = "rb+",
) -> BinaryIO:
    path = tmp_path / "body"
    _ = path.write_bytes(content)
    return path.open(mode)


@pytest.fixture
def pipe_with_more_coming() -> Iterator[BinaryIO]:
    """A source with bytes on it and more to come: a pipe still open at the far end.

    Opened unbuffered, so a read is one read of the pipe and comes back with
    whatever has arrived rather than with everything that was asked for.
    """
    reading, writing = os.pipe()
    _ = os.write(writing, b"first")
    opened = cast("BinaryIO", os.fdopen(reading, "rb", buffering=0))
    yield opened
    opened.close()
    os.close(writing)


async def _read(stream: Stream) -> object:
    return await stream.read(10)


async def _write(stream: Stream) -> object:
    return await stream.write(b"bar")


async def _seek(stream: Stream) -> object:
    return await stream.seek(10)


async def _tell(stream: Stream) -> object:
    # Reporting the cursor is not awaited; the signature is, so that one list
    # can name every operation a refusing stream is put through.
    return stream.tell()


async def _get_contents(stream: Stream) -> object:
    return await stream.get_contents()


async def _rewind(stream: Stream) -> object:
    return await stream.rewind()


def test_stream_is_a_stream() -> None:
    assert StreamInterface in Stream.__mro__


def test_a_stream_declares_no_whole_body_shortcut() -> None:
    # The whole of a body is read by awaiting `get_contents`; a conversion to
    # bytes could not await, so there is none to reach for by mistake.
    assert not hasattr(Stream, "__bytes__")


def test_metadata_reads_the_mode_of_a_write_only_buffer_as_writing_only() -> None:
    with UnreadableFile() as file:
        assert Stream(file).get_metadata("mode") == "wb"


async def test_create_over_bytes_reads_them_back() -> None:
    stream = Stream.create(b"data")

    assert await stream.get_contents() == b"data"


async def test_create_with_nothing_is_empty() -> None:
    assert await Stream.create().get_contents() == b""


async def test_create_over_a_lot_of_bytes_reads_them_all_back() -> None:
    content = b"Hello" * 50_000

    stream = Stream.create(content)

    assert await stream.get_contents() == content


def test_create_over_a_stream_hands_the_same_one_back() -> None:
    stream = Stream.create(b"data")

    assert Stream.create(stream) is stream


def test_a_stream_over_a_file_object_opened_to_read_and_write_is_readable(tmp_path: Path) -> None:
    with _file(tmp_path, b"data") as file:
        assert Stream(file).is_readable() is True


def test_a_stream_over_a_file_object_opened_to_read_and_write_is_writable(tmp_path: Path) -> None:
    with _file(tmp_path, b"data") as file:
        assert Stream(file).is_writable() is True


def test_a_stream_over_a_file_object_opened_to_read_and_write_is_seekable(tmp_path: Path) -> None:
    with _file(tmp_path, b"data") as file:
        assert Stream(file).is_seekable() is True


def test_a_stream_over_a_file_object_opened_to_read_only_is_not_writable(tmp_path: Path) -> None:
    with _file(tmp_path, b"data", "rb") as file:
        assert Stream(file).is_writable() is False


def test_a_stream_over_a_file_object_opened_to_write_only_is_not_readable(tmp_path: Path) -> None:
    with _file(tmp_path, b"", "wb") as file:
        assert Stream(file).is_readable() is False


def test_a_stream_over_an_unseekable_file_object_is_not_seekable() -> None:
    with UnseekableFile(b"data") as file:
        assert Stream(file).is_seekable() is False


def test_metadata_reports_the_path_the_file_was_opened_on(tmp_path: Path) -> None:
    with _file(tmp_path, b"data") as file:
        assert Stream(file).get_metadata("uri") == str(tmp_path / "body")


def test_metadata_reports_no_path_for_a_buffer_over_bytes() -> None:
    assert Stream.create(b"data").get_metadata("uri") is None


def test_metadata_reports_the_mode_the_file_was_opened_in(tmp_path: Path) -> None:
    with _file(tmp_path, b"data", "rb") as file:
        assert Stream(file).get_metadata("mode") == "rb"


def test_metadata_reads_the_mode_of_a_buffer_off_what_it_allows() -> None:
    assert Stream.create(b"data").get_metadata("mode") == "rb+"


def test_metadata_reads_the_mode_of_a_write_only_buffer_off_what_it_allows(tmp_path: Path) -> None:
    with _file(tmp_path, b"", "wb") as file:
        assert Stream(file).get_metadata("mode") == "wb"


def test_metadata_reports_whether_the_cursor_moves() -> None:
    with UnseekableFile(b"data") as file:
        assert Stream(file).get_metadata("seekable") is False


def test_metadata_with_no_key_is_every_entry() -> None:
    assert Stream.create(b"data").get_metadata() == {
        "mode": "rb+",
        "seekable": True,
        "uri": None,
    }


def test_metadata_has_nothing_under_an_unknown_key() -> None:
    assert Stream.create(b"data").get_metadata("wrapper_type") is None


def test_get_size_reports_the_bytes_there_are(tmp_path: Path) -> None:
    with _file(tmp_path, b"data") as file:
        assert Stream(file).get_size() == 4


def test_get_size_asked_twice_gives_the_same_answer(tmp_path: Path) -> None:
    with _file(tmp_path, b"data") as file:
        stream = Stream(file)

        assert (stream.get_size(), stream.get_size()) == (4, 4)


async def test_get_size_leaves_the_cursor_where_it_was() -> None:
    stream = Stream.create(b"data")
    await stream.seek(2)

    _ = stream.get_size()

    assert stream.tell() == 2


async def test_get_size_follows_a_write() -> None:
    stream = Stream.create(b"foo")
    await stream.seek(0, os.SEEK_END)

    assert await stream.write(b"test") == 4
    assert stream.get_size() == 7


def test_get_size_of_an_unseekable_stream_is_unknown() -> None:
    with UnseekableFile(b"data") as file:
        assert Stream(file).get_size() is None


async def test_a_stream_just_written_to_has_not_reached_its_end() -> None:
    stream = Stream.create()
    _ = await stream.write(b"data")

    assert stream.eof() is False


async def test_a_read_that_finds_the_end_reaches_it() -> None:
    stream = Stream.create()
    _ = await stream.write(b"data")

    _ = await stream.read(4)

    assert stream.eof() is True


async def test_a_read_that_runs_out_of_a_stream_it_can_measure_reaches_its_end() -> None:
    stream = Stream.create(b"data")

    _ = await stream.read(10)

    assert stream.eof() is True


async def test_a_read_that_comes_back_short_of_a_source_with_more_coming_finds_no_end(
    pipe_with_more_coming: BinaryIO,
) -> None:
    stream = Stream(pipe_with_more_coming)

    assert await stream.read(4096) == b"first"
    assert stream.eof() is False


async def test_a_seek_puts_the_end_back_out_of_reach() -> None:
    stream = Stream.create(b"data")
    _ = await stream.get_contents()

    await stream.seek(0)

    assert stream.eof() is False


def test_tell_starts_at_the_beginning() -> None:
    assert Stream.create().tell() == 0


async def test_tell_follows_a_write() -> None:
    stream = Stream.create()
    _ = await stream.write(b"foo")

    assert stream.tell() == 3


async def test_tell_follows_a_seek() -> None:
    stream = Stream.create(b"foo")

    await stream.seek(1)

    assert stream.tell() == 1


async def test_tell_agrees_with_the_file_object(tmp_path: Path) -> None:
    with _file(tmp_path, b"foo") as file:
        stream = Stream(file)
        await stream.seek(1)

        assert stream.tell() == file.tell()


async def test_rewind_goes_back_to_the_beginning() -> None:
    stream = Stream.create(b"data")
    _ = await stream.read(4)

    await stream.rewind()

    assert stream.tell() == 0


async def test_get_contents_rewinds_before_reading_the_whole_stream() -> None:
    stream = Stream.create(b"data")
    await stream.seek(2)

    assert await stream.get_contents() == b"data"


async def test_get_contents_at_the_end_rewinds_and_reads_everything() -> None:
    stream = Stream.create(b"data")
    await stream.seek(0, os.SEEK_END)

    assert await stream.get_contents() == b"data"


async def test_get_contents_can_be_taken_more_than_once() -> None:
    stream = Stream.create(b"data")

    assert (await stream.get_contents(), await stream.get_contents()) == (b"data", b"data")


async def test_get_contents_of_an_unseekable_stream_reads_from_the_cursor() -> None:
    # There is nothing to rewind to, so the cursor is where the read starts.
    with UnseekableFile(b"data") as file:
        stream = Stream(file)
        _ = await stream.read(2)

        assert await stream.get_contents() == b"ta"


async def test_get_contents_of_an_unseekable_stream_a_second_time_reads_nothing() -> None:
    with UnseekableFile(b"data") as file:
        stream = Stream(file)
        _ = await stream.get_contents()

        assert await stream.get_contents() == b""


async def test_read_takes_at_most_what_was_asked_for() -> None:
    assert await Stream.create(b"data").read(2) == b"da"


def test_detach_hands_the_file_object_out(tmp_path: Path) -> None:
    with _file(tmp_path, b"data") as file:
        assert Stream(file).detach() is file


def test_detach_a_second_time_hands_nothing_out() -> None:
    stream = Stream.create(b"data")
    _ = stream.detach()

    assert stream.detach() is None


@pytest.mark.parametrize(
    "what",
    [
        pytest.param(_read, id="read"),
        pytest.param(_write, id="write"),
        pytest.param(_seek, id="seek"),
        pytest.param(_tell, id="tell"),
        pytest.param(_get_contents, id="get_contents"),
        pytest.param(_rewind, id="rewind"),
    ],
)
async def test_a_detached_stream_refuses_to_work(
    what: Callable[[Stream], Awaitable[object]],
) -> None:
    stream = Stream(io.BytesIO(b"data"))
    _ = stream.detach()

    with pytest.raises(StreamError, match="Stream is detached"):
        _ = await what(stream)


def test_a_detached_stream_can_do_nothing() -> None:
    stream = Stream.create(b"data")
    assert isinstance(stream, Stream)
    _ = stream.detach()

    assert (stream.is_readable(), stream.is_writable(), stream.is_seekable()) == (
        False,
        False,
        False,
    )


def test_a_detached_stream_is_at_its_end() -> None:
    stream = Stream.create(b"data")
    _ = stream.detach()

    assert stream.eof() is True


def test_a_detached_stream_has_no_size() -> None:
    stream = Stream.create(b"data")
    _ = stream.detach()

    assert stream.get_size() is None


async def test_get_contents_of_a_detached_stream_is_refused() -> None:
    stream = Stream.create(b"data")
    _ = stream.detach()

    with pytest.raises(StreamError, match="Stream is detached"):
        _ = await stream.get_contents()


def test_a_detached_stream_has_no_metadata() -> None:
    stream = Stream.create(b"data")
    _ = stream.detach()

    assert stream.get_metadata() == {}


def test_a_detached_stream_has_nothing_under_a_metadata_key() -> None:
    stream = Stream.create(b"data")
    _ = stream.detach()

    assert stream.get_metadata("mode") is None


async def test_closing_clears_what_the_stream_could_do(tmp_path: Path) -> None:
    with _file(tmp_path, b"data") as file:
        stream = Stream(file)

        await stream.close()

        assert (stream.is_readable(), stream.is_writable(), stream.is_seekable()) == (
            False,
            False,
            False,
        )


async def test_closing_closes_the_file_object(tmp_path: Path) -> None:
    with _file(tmp_path, b"data") as file:
        await Stream(file).close()

        assert file.closed is True


async def test_closing_twice_is_harmless() -> None:
    stream = Stream.create(b"data")

    await stream.close()
    await stream.close()

    assert stream.get_size() is None


def test_dropping_a_stream_leaves_the_file_object_open(tmp_path: Path) -> None:
    with _file(tmp_path, b"data") as file:
        stream = Stream(file)

        del stream

        assert file.closed is False


async def test_writing_to_an_unwritable_stream_is_refused(tmp_path: Path) -> None:
    with _file(tmp_path, b"data", "rb") as file, pytest.raises(StreamError, match="non-writable"):
        _ = await Stream(file).write(b"nope")


async def test_reading_from_an_unreadable_stream_is_refused(tmp_path: Path) -> None:
    with _file(tmp_path, b"", "wb") as file, pytest.raises(StreamError, match="non-readable"):
        _ = await Stream(file).read(1)


async def test_seeking_an_unseekable_stream_is_refused() -> None:
    with UnseekableFile(b"data") as file, pytest.raises(StreamError, match="not seekable"):
        await Stream(file).seek(0)


async def test_get_contents_of_an_unreadable_stream_is_refused(tmp_path: Path) -> None:
    with (
        _file(tmp_path, b"", "wb") as file,
        pytest.raises(StreamError, match="Unable to read stream contents"),
    ):
        _ = await Stream(file).get_contents()


async def test_a_body_can_be_copied_a_mebibyte_at_a_time() -> None:
    stream = Stream.create(b"x" * (_ONE_MIB + 7))
    read = b""

    while not stream.eof():
        read += await stream.read(_ONE_MIB)

    assert len(read) == _ONE_MIB + 7


def test_a_stream_whose_file_was_closed_behind_its_back_can_do_nothing(tmp_path: Path) -> None:
    file = _file(tmp_path, b"data")
    stream = Stream(file)
    file.close()

    assert (stream.is_readable(), stream.is_writable(), stream.is_seekable()) == (
        False,
        False,
        False,
    )


@pytest.mark.parametrize(
    ("what", "refusal"),
    [
        pytest.param(_read, "non-readable", id="read"),
        pytest.param(_write, "non-writable", id="write"),
        pytest.param(_seek, "not seekable", id="seek"),
        pytest.param(_rewind, "not seekable", id="rewind"),
        pytest.param(_tell, "Unable to determine stream position", id="tell"),
        pytest.param(_get_contents, "Unable to read stream contents", id="get_contents"),
    ],
)
async def test_a_stream_whose_file_was_closed_behind_its_back_refuses_to_work(
    tmp_path: Path,
    what: Callable[[Stream], Awaitable[object]],
    refusal: str,
) -> None:
    file = _file(tmp_path, b"data")
    stream = Stream(file)
    file.close()

    with pytest.raises(StreamError, match=refusal):
        _ = await what(stream)


def test_a_stream_whose_file_was_closed_behind_its_back_has_no_size(tmp_path: Path) -> None:
    file = _file(tmp_path, b"data")
    stream = Stream(file)
    file.close()

    assert stream.get_size() is None


async def test_get_contents_of_a_stream_whose_file_was_closed_behind_its_back_is_refused(
    tmp_path: Path,
) -> None:
    file = _file(tmp_path, b"data")
    stream = Stream(file)
    file.close()

    with pytest.raises(StreamError, match="Unable to read stream contents"):
        _ = await stream.get_contents()


@pytest.mark.parametrize(
    ("what", "refusal"),
    [
        pytest.param(_seek, 'Unable to seek to stream position "10" with whence 0', id="seek"),
        pytest.param(_write, "Unable to write to stream", id="write"),
        pytest.param(_read, "Unable to read from stream", id="read"),
        pytest.param(_rewind, 'Unable to seek to stream position "0" with whence 0', id="rewind"),
    ],
)
async def test_a_stream_over_a_file_that_fails_under_it_says_what_did_not_work(
    what: Callable[[Stream], Awaitable[object]],
    refusal: str,
) -> None:
    # The file reports itself open, seekable, readable and writable, so every
    # check a stream makes before using it passes; the operation itself is
    # what fails.
    stream = Stream(BrokenFile(b"data"))

    with pytest.raises(StreamError, match=re.escape(refusal)):
        _ = await what(stream)


async def test_get_contents_of_a_stream_over_a_file_that_fails_under_it_is_refused() -> None:
    # Reading the whole of a stream rewinds it first, so a cursor that will
    # not move is what gives way before the read is even reached.
    refusal = 'Unable to seek to stream position "0" with whence 0'

    with pytest.raises(StreamError, match=re.escape(refusal)):
        _ = await Stream(BrokenFile(b"data")).get_contents()
