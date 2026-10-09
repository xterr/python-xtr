"""The contract tests of the fakes the other tests build on.

A fake that drifts from what it stands in for turns every test that uses it
into a test of nothing, so each one is held to the promise its name makes.
"""

from __future__ import annotations

import pytest

from tests.support.broken_file import BrokenFile
from tests.support.endless_stream import EndlessStream
from tests.support.unreadable_file import UnreadableFile
from tests.support.unseekable_file import UnseekableFile


def test_the_unseekable_file_does_not_seek() -> None:
    with UnseekableFile(b"data") as file:
        assert file.seekable() is False


def test_the_unseekable_file_still_reads_what_it_holds() -> None:
    with UnseekableFile(b"data") as file:
        assert file.read() == b"data"


def test_the_unreadable_file_does_not_read() -> None:
    with UnreadableFile() as file:
        assert file.readable() is False


def test_the_unreadable_file_still_takes_what_is_written_to_it() -> None:
    with UnreadableFile() as file:
        assert file.write(b"data") == 4


def test_the_endless_stream_never_reaches_its_end() -> None:
    stream = EndlessStream(b"data")

    _ = stream.get_contents()

    assert stream.eof() is False


def test_the_endless_stream_does_not_seek() -> None:
    assert EndlessStream(b"data").is_seekable() is False


def test_the_endless_stream_refuses_to_move_its_cursor() -> None:
    with pytest.raises(RuntimeError, match="not seekable"):
        EndlessStream(b"data").seek(0)


def test_the_endless_stream_refuses_to_rewind() -> None:
    with pytest.raises(RuntimeError, match="not seekable"):
        EndlessStream(b"data").rewind()


def test_the_endless_stream_reads_what_it_holds_once() -> None:
    stream = EndlessStream(b"data")

    assert (stream.read(4), stream.read(4)) == (b"data", b"")


def test_the_endless_stream_reads_the_whole_of_what_it_holds() -> None:
    assert bytes(EndlessStream(b"data")) == b"data"


def test_the_endless_stream_reports_the_size_of_what_it_holds() -> None:
    assert EndlessStream(b"data").get_size() == 4


def test_the_endless_stream_starts_at_the_beginning() -> None:
    assert EndlessStream(b"data").tell() == 0


def test_the_endless_stream_reads_and_writes() -> None:
    stream = EndlessStream(b"data")

    assert (stream.is_readable(), stream.is_writable()) == (True, True)


def test_the_endless_stream_takes_what_is_written_to_it() -> None:
    stream = EndlessStream(b"")

    assert stream.write(b"more") == 4


def test_the_endless_stream_knows_what_it_is_over() -> None:
    assert EndlessStream(b"data").get_metadata("mode") == "rb+"


def test_the_endless_stream_can_be_detached() -> None:
    stream = EndlessStream(b"data")

    detached = stream.detach()

    assert detached is not None
    detached.close()


def test_the_endless_stream_can_be_closed() -> None:
    stream = EndlessStream(b"data")

    stream.close()

    assert stream.get_size() is None


def test_the_broken_file_reports_that_it_can_do_everything() -> None:
    with BrokenFile(b"data") as file:
        assert (file.closed, file.seekable(), file.readable(), file.writable()) == (
            False,
            True,
            True,
            True,
        )


def test_the_broken_file_refuses_to_move_its_cursor() -> None:
    with BrokenFile(b"data") as file, pytest.raises(OSError, match="gone away"):
        _ = file.seek(0)


def test_the_broken_file_refuses_to_read() -> None:
    with BrokenFile(b"data") as file, pytest.raises(OSError, match="gone away"):
        _ = file.read(4)


def test_the_broken_file_refuses_to_write() -> None:
    with BrokenFile(b"data") as file, pytest.raises(OSError, match="gone away"):
        _ = file.write(b"more")
