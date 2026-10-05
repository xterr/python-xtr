from __future__ import annotations

from xtr_storage.exception import (
    StorageError,
    UnableToCheckExistenceError,
    UnableToCheckFileExistenceError,
)
from xtr_storage.operation import Operation


def test_it_carries_the_location() -> None:
    error = UnableToCheckFileExistenceError("photos/a.jpg")

    assert error.location == "photos/a.jpg"
    assert str(error) == "unable to check whether 'photos/a.jpg' exists"


def test_it_is_caught_as_an_existence_check() -> None:
    error = UnableToCheckFileExistenceError("photos/a.jpg")

    assert isinstance(error, StorageError)
    assert isinstance(error, UnableToCheckExistenceError)


def test_it_is_a_failed_file_check() -> None:
    error = UnableToCheckFileExistenceError("photos/a.jpg")

    assert error.operation is Operation.FILE_EXISTS
