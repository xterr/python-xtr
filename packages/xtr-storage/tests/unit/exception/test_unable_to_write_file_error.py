from __future__ import annotations

from xtr_storage.exception import (
    StorageError,
    StorageOperationFailedError,
    UnableToWriteFileError,
)
from xtr_storage.operation import Operation


def test_it_carries_the_location_and_the_reason() -> None:
    error = UnableToWriteFileError("photos/a.jpg", "the bucket is full")

    assert error.location == "photos/a.jpg"
    assert error.reason == "the bucket is full"


def test_its_message_names_the_location_and_the_reason() -> None:
    error = UnableToWriteFileError("photos/a.jpg", "the bucket is full")

    assert str(error) == "unable to write the file 'photos/a.jpg': the bucket is full"


def test_it_reads_without_a_reason() -> None:
    error = UnableToWriteFileError("photos/a.jpg")

    assert error.reason == ""
    assert str(error) == "unable to write the file 'photos/a.jpg'"


def test_it_is_a_failed_write() -> None:
    error = UnableToWriteFileError("photos/a.jpg")

    assert isinstance(error, StorageError)
    assert isinstance(error, StorageOperationFailedError)
    assert error.operation is Operation.WRITE
