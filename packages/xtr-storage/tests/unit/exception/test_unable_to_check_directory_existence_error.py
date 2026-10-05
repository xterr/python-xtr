from __future__ import annotations

from xtr_storage.exception import (
    StorageError,
    UnableToCheckDirectoryExistenceError,
    UnableToCheckExistenceError,
)
from xtr_storage.operation import Operation


def test_it_carries_the_location() -> None:
    error = UnableToCheckDirectoryExistenceError("photos")

    assert error.location == "photos"
    assert str(error) == "unable to check whether 'photos' exists"


def test_it_is_caught_as_an_existence_check() -> None:
    error = UnableToCheckDirectoryExistenceError("photos")

    assert isinstance(error, StorageError)
    assert isinstance(error, UnableToCheckExistenceError)


def test_it_is_a_failed_directory_check() -> None:
    error = UnableToCheckDirectoryExistenceError("photos")

    assert error.operation is Operation.DIRECTORY_EXISTS
