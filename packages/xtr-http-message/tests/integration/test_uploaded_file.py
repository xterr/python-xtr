from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from xtr_http_message_contracts import StreamInterface, UploadError

from xtr_http_message.exception import UploadedFileError

from .conftest import UPLOADED_PAYLOAD

if TYPE_CHECKING:
    from pathlib import Path

    from xtr_http_message_contracts import UploadedFileInterface

pytestmark = pytest.mark.anyio


def test_the_contents_of_an_upload_are_read_as_a_stream(
    uploaded_file: UploadedFileInterface,
) -> None:
    assert isinstance(uploaded_file.get_stream(), StreamInterface)


async def test_the_contents_cannot_be_read_once_the_file_has_been_moved(
    uploaded_file: UploadedFileInterface,
    tmp_path: Path,
) -> None:
    await uploaded_file.move_to(str(tmp_path / "foo"))

    with pytest.raises(UploadedFileError):
        _ = uploaded_file.get_stream()


async def test_an_upload_is_moved_to_an_absolute_path(
    uploaded_file: UploadedFileInterface,
    tmp_path: Path,
) -> None:
    target = tmp_path / "foo"

    assert target.is_file() is False
    await uploaded_file.move_to(str(target))
    assert target.is_file() is True


async def test_an_upload_is_moved_to_a_relative_path(
    uploaded_file: UploadedFileInterface,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The harness moves to an absolute path here too; this one is relative in fact.

    Which is what its name asks for, and the working directory is moved to a
    directory of the run so that nothing is written beside the sources.
    """
    monkeypatch.chdir(tmp_path)

    await uploaded_file.move_to("foo")

    assert (tmp_path / "foo").is_file() is True


async def test_an_upload_cannot_be_moved_twice(
    uploaded_file: UploadedFileInterface,
    tmp_path: Path,
) -> None:
    await uploaded_file.move_to(str(tmp_path / "foo"))

    with pytest.raises(UploadedFileError):
        await uploaded_file.move_to(str(tmp_path / "bar"))


def test_the_size_of_an_upload_is_counted(uploaded_file: UploadedFileInterface) -> None:
    """The harness takes either a count or nothing; the factory counts the stream."""
    assert uploaded_file.get_size() == len(UPLOADED_PAYLOAD)


def test_an_upload_that_arrived_whole_records_no_error(
    uploaded_file: UploadedFileInterface,
) -> None:
    assert uploaded_file.get_error() == UploadError.OK


def test_an_upload_the_client_named_nothing_for_has_no_file_name(
    uploaded_file: UploadedFileInterface,
) -> None:
    """The harness takes either a name or nothing; nothing was sent with this one."""
    assert uploaded_file.get_client_filename() is None


def test_an_upload_the_client_typed_nothing_for_has_no_media_type(
    uploaded_file: UploadedFileInterface,
) -> None:
    """The harness takes either a type or nothing; nothing was sent with this one."""
    assert uploaded_file.get_client_media_type() is None
