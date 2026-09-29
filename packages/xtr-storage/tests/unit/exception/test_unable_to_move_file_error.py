from __future__ import annotations

from xtr_storage.exception import (
    StorageError,
    StorageOperationFailedError,
    UnableToMoveFileError,
)
from xtr_storage.operation import Operation


def test_it_carries_both_paths_and_the_reason() -> None:
    error = UnableToMoveFileError("photos/a.jpg", "archive/a.jpg", "the copy failed")

    assert error.source == "photos/a.jpg"
    assert error.destination == "archive/a.jpg"
    assert error.reason == "the copy failed"


def test_its_message_names_both_paths_and_the_reason() -> None:
    error = UnableToMoveFileError("photos/a.jpg", "archive/a.jpg", "the copy failed")

    assert str(error) == "unable to move 'photos/a.jpg' to 'archive/a.jpg': the copy failed"


def test_it_reads_without_a_reason() -> None:
    error = UnableToMoveFileError("photos/a.jpg", "archive/a.jpg")

    assert error.reason == ""
    assert str(error) == "unable to move 'photos/a.jpg' to 'archive/a.jpg'"


def test_it_is_a_failed_move() -> None:
    error = UnableToMoveFileError("photos/a.jpg", "archive/a.jpg")

    assert isinstance(error, StorageError)
    assert isinstance(error, StorageOperationFailedError)
    assert error.operation is Operation.MOVE
