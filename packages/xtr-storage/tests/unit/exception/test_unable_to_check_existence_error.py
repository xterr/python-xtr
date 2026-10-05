from __future__ import annotations

from xtr_storage.exception import (
    StorageError,
    StorageOperationFailedError,
    UnableToCheckExistenceError,
)
from xtr_storage.operation import Operation


def test_it_carries_the_location() -> None:
    error = UnableToCheckExistenceError("photos/a.jpg")

    assert error.location == "photos/a.jpg"


def test_its_message_names_the_location() -> None:
    error = UnableToCheckExistenceError("photos/a.jpg")

    assert str(error) == "unable to check whether 'photos/a.jpg' exists"


def test_it_is_a_failed_existence_check() -> None:
    error = UnableToCheckExistenceError("photos/a.jpg")

    assert isinstance(error, StorageError)
    assert isinstance(error, StorageOperationFailedError)
    assert error.operation is Operation.EXISTENCE_CHECK
