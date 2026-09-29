from __future__ import annotations

from xtr_storage.exception import (
    StorageError,
    StorageOperationFailedError,
    UnableToReadFileError,
)
from xtr_storage.operation import Operation


def test_it_carries_the_location_and_the_reason() -> None:
    error = UnableToReadFileError("photos/a.jpg", "the object is gone")

    assert error.location == "photos/a.jpg"
    assert error.reason == "the object is gone"


def test_its_message_names_the_location_and_the_reason() -> None:
    error = UnableToReadFileError("photos/a.jpg", "the object is gone")

    assert str(error) == "unable to read the file 'photos/a.jpg': the object is gone"


def test_it_reads_without_a_reason() -> None:
    error = UnableToReadFileError("photos/a.jpg")

    assert error.reason == ""
    assert str(error) == "unable to read the file 'photos/a.jpg'"


def test_it_is_a_failed_read() -> None:
    error = UnableToReadFileError("photos/a.jpg")

    assert isinstance(error, StorageError)
    assert isinstance(error, StorageOperationFailedError)
    assert error.operation is Operation.READ
