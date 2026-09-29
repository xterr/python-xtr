from __future__ import annotations

from xtr_storage.exception import (
    StorageError,
    StorageOperationFailedError,
    SymbolicLinkEncounteredError,
)


def test_it_carries_the_location_of_the_link() -> None:
    error = SymbolicLinkEncounteredError("photos/elsewhere")

    assert error.location == "photos/elsewhere"


def test_its_message_names_the_link() -> None:
    error = SymbolicLinkEncounteredError("photos/elsewhere")

    assert str(error) == "unsupported symbolic link encountered at 'photos/elsewhere'"


def test_it_is_a_storage_error_but_not_a_failed_operation() -> None:
    error = SymbolicLinkEncounteredError("photos/elsewhere")

    assert isinstance(error, StorageError)
    assert not isinstance(error, StorageOperationFailedError)
