from __future__ import annotations

from xtr_storage.exception import (
    StorageError,
    StorageOperationFailedError,
    UnableToCopyFileError,
)
from xtr_storage.operation import Operation


def test_it_carries_both_paths_and_the_reason() -> None:
    error = UnableToCopyFileError("photos/a.jpg", "archive/a.jpg", "the read stopped")

    assert error.source == "photos/a.jpg"
    assert error.destination == "archive/a.jpg"
    assert error.reason == "the read stopped"


def test_its_message_names_both_paths_and_the_reason() -> None:
    error = UnableToCopyFileError("photos/a.jpg", "archive/a.jpg", "the read stopped")

    assert str(error) == "unable to copy 'photos/a.jpg' to 'archive/a.jpg': the read stopped"


def test_it_reads_without_a_reason() -> None:
    error = UnableToCopyFileError("photos/a.jpg", "archive/a.jpg")

    assert error.reason == ""
    assert str(error) == "unable to copy 'photos/a.jpg' to 'archive/a.jpg'"


def test_it_is_a_failed_copy() -> None:
    error = UnableToCopyFileError("photos/a.jpg", "archive/a.jpg")

    assert isinstance(error, StorageError)
    assert isinstance(error, StorageOperationFailedError)
    assert error.operation is Operation.COPY
