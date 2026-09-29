from __future__ import annotations

from xtr_storage.exception import (
    StorageError,
    StorageOperationFailedError,
    UnableToCreateDirectoryError,
)
from xtr_storage.operation import Operation


def test_it_carries_the_location_and_the_reason() -> None:
    error = UnableToCreateDirectoryError("photos/2026", "a file is in the way")

    assert error.location == "photos/2026"
    assert error.reason == "a file is in the way"


def test_its_message_names_the_location_and_the_reason() -> None:
    error = UnableToCreateDirectoryError("photos/2026", "a file is in the way")

    assert str(error) == "unable to create the directory 'photos/2026': a file is in the way"


def test_it_reads_without_a_reason() -> None:
    error = UnableToCreateDirectoryError("photos/2026")

    assert error.reason == ""
    assert str(error) == "unable to create the directory 'photos/2026'"


def test_it_is_a_failed_directory_creation() -> None:
    error = UnableToCreateDirectoryError("photos/2026")

    assert isinstance(error, StorageError)
    assert isinstance(error, StorageOperationFailedError)
    assert error.operation is Operation.CREATE_DIRECTORY
