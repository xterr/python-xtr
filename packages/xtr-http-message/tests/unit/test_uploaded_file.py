from __future__ import annotations

import io
import re
from typing import TYPE_CHECKING

import pytest
from xtr_http_message_contracts import StreamInterface, UploadedFileInterface, UploadError

from tests.support.endless_stream import EndlessStream
from xtr_http_message.exception import InvalidArgumentError, UploadedFileError
from xtr_http_message.factory.http_factory import HttpFactory
from xtr_http_message.stream import Stream
from xtr_http_message.uploaded_file import UploadedFile

if TYPE_CHECKING:
    from pathlib import Path

_FAILED = [
    pytest.param(error, id=error.name) for error in UploadError if error is not UploadError.OK
]


def test_uploaded_file_is_an_uploaded_file() -> None:
    assert UploadedFileInterface in UploadedFile.__mro__


def test_an_upload_that_went_through_with_nothing_to_read_is_refused() -> None:
    with pytest.raises(
        InvalidArgumentError,
        match="Invalid stream or file provided for UploadedFile",
    ):
        _ = UploadedFile("", 0, UploadError.OK)


@pytest.mark.parametrize("error", [-1, 5, 9])
def test_an_outcome_that_is_not_an_upload_outcome_is_refused(error: int) -> None:
    with pytest.raises(InvalidArgumentError, match="status"):
        _ = UploadedFile(Stream.create(), 0, error)


def test_a_file_that_arrived_as_a_stream_reads_back_as_that_very_stream() -> None:
    stream = Stream.create(b"")

    assert UploadedFile(stream, 0, UploadError.OK).get_stream() is stream


def test_a_file_that_arrived_as_a_file_object_reads_back_over_it() -> None:
    with io.BytesIO(b"") as file:
        upload = UploadedFile(file, 0, UploadError.OK)

        assert upload.get_stream().detach() is file


def test_a_file_that_arrived_as_a_path_is_opened_when_it_is_read(tmp_path: Path) -> None:
    path = tmp_path / "foo.txt"
    _ = path.write_bytes(b"Foobar\n")

    stream = UploadedFile(str(path), 7, UploadError.OK).get_stream()

    try:
        assert (isinstance(stream, StreamInterface), bytes(stream)) == (True, b"Foobar\n")
    finally:
        stream.close()


def test_a_file_that_arrived_as_a_path_is_opened_afresh_every_time(tmp_path: Path) -> None:
    path = tmp_path / "foo.txt"
    _ = path.write_bytes(b"Foobar\n")
    upload = UploadedFile(str(path), 7, UploadError.OK)

    first, second = upload.get_stream(), upload.get_stream()

    try:
        assert first is not second
    finally:
        first.close()
        second.close()


def test_a_path_that_cannot_be_opened_is_reported_with_the_path(tmp_path: Path) -> None:
    missing = str(tmp_path / "gone.txt")

    with pytest.raises(
        UploadedFileError,
        match=re.escape(f'The file "{missing}" cannot be opened'),
    ):
        _ = UploadedFile(missing, 0, UploadError.OK).get_stream()


def test_what_the_client_sent_is_recorded_as_it_arrived() -> None:
    stream = Stream.create(b"Foo bar!")

    upload = UploadedFile(stream, stream.get_size(), UploadError.OK, "filename.txt", "text/plain")

    assert (
        upload.get_size(),
        upload.get_client_filename(),
        upload.get_client_media_type(),
        upload.get_error(),
    ) == (8, "filename.txt", "text/plain", UploadError.OK)


def test_a_size_nobody_counted_is_unknown() -> None:
    assert UploadedFile(Stream.create(b"Foo bar!"), None, UploadError.OK).get_size() is None


def test_a_file_the_client_named_nothing_has_no_name() -> None:
    upload = UploadedFile(Stream.create(b"Foo bar!"), 8, UploadError.OK)

    assert (upload.get_client_filename(), upload.get_client_media_type()) == (None, None)


def test_moving_a_file_that_arrived_as_a_stream_writes_it_where_it_was_told(
    tmp_path: Path,
) -> None:
    stream = Stream.create(b"Foo bar!")
    upload = UploadedFile(stream, stream.get_size(), UploadError.OK, "filename.txt", "text/plain")
    target = tmp_path / "moved.txt"

    upload.move_to(str(target))

    assert target.read_bytes() == b"Foo bar!"


def test_moving_a_file_larger_than_one_chunk_writes_all_of_it(tmp_path: Path) -> None:
    content = b"x" * (1_048_576 + 7)
    upload = UploadedFile(Stream.create(content), len(content), UploadError.OK)
    target = tmp_path / "moved.bin"

    upload.move_to(str(target))

    assert target.read_bytes() == content


def test_moving_a_file_finishes_against_a_stream_that_never_reaches_its_end(
    tmp_path: Path,
) -> None:
    upload = UploadedFile(EndlessStream(b"Foo bar!"), 8, UploadError.OK)
    target = tmp_path / "moved.txt"

    upload.move_to(str(target))

    assert target.read_bytes() == b"Foo bar!"


def test_moving_a_file_rewinds_a_stream_already_read(tmp_path: Path) -> None:
    stream = Stream.create(b"Foo bar!")
    _ = stream.get_contents()
    upload = UploadedFile(stream, 8, UploadError.OK)
    target = tmp_path / "moved.txt"

    upload.move_to(str(target))

    assert target.read_bytes() == b"Foo bar!"


def test_moving_a_file_to_an_empty_path_is_refused() -> None:
    upload = UploadedFile(HttpFactory().create_stream(b"Foo bar!"), 0, UploadError.OK)

    with pytest.raises(InvalidArgumentError, match="path"):
        upload.move_to("")


def test_moving_a_file_to_a_path_that_cannot_be_opened_is_reported(tmp_path: Path) -> None:
    upload = UploadedFile(HttpFactory().create_stream(b"Foo bar!"), 8, UploadError.OK)
    target = str(tmp_path / "missing" / "moved.txt")

    with pytest.raises(
        UploadedFileError,
        match=re.escape(f'The file "{target}" cannot be opened'),
    ):
        upload.move_to(target)


def test_a_file_cannot_be_moved_twice(tmp_path: Path) -> None:
    upload = UploadedFile(HttpFactory().create_stream(b"Foo bar!"), 8, UploadError.OK)
    target = tmp_path / "moved.txt"
    upload.move_to(str(target))

    with pytest.raises(UploadedFileError, match="moved"):
        upload.move_to(str(target))


def test_a_file_cannot_be_read_once_it_has_been_moved(tmp_path: Path) -> None:
    upload = UploadedFile(HttpFactory().create_stream(b"Foo bar!"), 8, UploadError.OK)
    target = tmp_path / "moved.txt"
    upload.move_to(str(target))

    with pytest.raises(UploadedFileError, match="moved"):
        _ = upload.get_stream()


@pytest.mark.parametrize("error", _FAILED)
def test_an_upload_that_did_not_go_through_keeps_nothing_but_its_outcome(
    error: UploadError,
) -> None:
    assert UploadedFile("not ok", 0, error).get_error() == error


@pytest.mark.parametrize("error", _FAILED)
def test_an_upload_that_did_not_go_through_cannot_be_moved(
    error: UploadError,
    tmp_path: Path,
) -> None:
    upload = UploadedFile("not ok", 0, error)

    with pytest.raises(UploadedFileError, match="upload error"):
        upload.move_to(str(tmp_path / "moved.txt"))


@pytest.mark.parametrize("error", _FAILED)
def test_an_upload_that_did_not_go_through_cannot_be_read(error: UploadError) -> None:
    with pytest.raises(UploadedFileError, match="upload error"):
        _ = UploadedFile("not ok", 0, error).get_stream()


def test_moving_a_file_that_arrived_as_a_path_moves_the_file(tmp_path: Path) -> None:
    source = tmp_path / "from.txt"
    _ = source.write_bytes(b"Foo bar!")
    target = tmp_path / "to.txt"

    UploadedFile(str(source), 8, UploadError.OK, source.name, "text/plain").move_to(str(target))

    assert (target.read_bytes(), source.exists()) == (b"Foo bar!", False)


def test_moving_a_file_that_is_not_where_it_says_it_is_is_reported(tmp_path: Path) -> None:
    missing = str(tmp_path / "gone.txt")
    target = str(tmp_path / "to.txt")

    with pytest.raises(
        UploadedFileError,
        match=re.escape(f'Uploaded file could not be moved to "{target}"'),
    ):
        UploadedFile(missing, 0, UploadError.OK).move_to(target)
