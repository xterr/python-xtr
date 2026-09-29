from __future__ import annotations

from xtr_storage.exception import (
    PathTraversalDetectedError,
    StorageError,
    StorageOperationFailedError,
)


def test_it_carries_the_path() -> None:
    error = PathTraversalDetectedError("../etc/passwd")

    assert error.path == "../etc/passwd"


def test_its_message_names_the_path() -> None:
    error = PathTraversalDetectedError("../etc/passwd")

    assert str(error) == "path traversal detected in '../etc/passwd'"


def test_it_is_a_storage_error_but_not_a_failed_operation() -> None:
    error = PathTraversalDetectedError("../etc/passwd")

    assert isinstance(error, StorageError)
    assert not isinstance(error, StorageOperationFailedError)
