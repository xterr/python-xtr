from __future__ import annotations

from xtr_storage.exception import (
    StorageError,
    StorageOperationFailedError,
    UnableToDeleteDirectoryError,
)
from xtr_storage.operation import Operation


def test_it_carries_the_location_and_the_reason() -> None:
    error = UnableToDeleteDirectoryError("photos", "two keys were left behind")

    assert error.location == "photos"
    assert error.reason == "two keys were left behind"


def test_its_message_names_the_location_and_the_reason() -> None:
    error = UnableToDeleteDirectoryError("photos", "two keys were left behind")

    assert str(error) == "unable to delete the directory 'photos': two keys were left behind"


def test_it_reads_without_a_reason() -> None:
    error = UnableToDeleteDirectoryError("photos")

    assert error.reason == ""
    assert str(error) == "unable to delete the directory 'photos'"


def test_it_is_a_failed_directory_delete() -> None:
    error = UnableToDeleteDirectoryError("photos")

    assert isinstance(error, StorageError)
    assert isinstance(error, StorageOperationFailedError)
    assert error.operation is Operation.DELETE_DIRECTORY
