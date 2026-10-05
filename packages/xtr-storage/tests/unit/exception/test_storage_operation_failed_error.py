from __future__ import annotations

import pytest

from xtr_storage.exception import (
    StorageError,
    StorageOperationFailedError,
    UnableToReadFileError,
)
from xtr_storage.operation import Operation


def test_it_is_a_storage_error() -> None:
    assert issubclass(StorageOperationFailedError, StorageError)


def test_it_leaves_the_operation_for_its_subclasses_to_set() -> None:
    with pytest.raises(AttributeError):
        _ = StorageOperationFailedError.operation


def test_a_failed_operation_names_the_operation_it_was() -> None:
    error = UnableToReadFileError("photos/a.jpg")

    assert isinstance(error, StorageOperationFailedError)
    assert error.operation is Operation.READ
