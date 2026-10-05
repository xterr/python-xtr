from __future__ import annotations

from xtr_storage.exception import (
    StorageError,
    StorageOperationFailedError,
    UnableToProvideChecksumError,
)


def test_it_carries_the_location_and_the_reason() -> None:
    error = UnableToProvideChecksumError("photos/a.jpg", "the file could not be read")

    assert error.location == "photos/a.jpg"
    assert error.reason == "the file could not be read"


def test_its_message_names_the_location_and_the_reason() -> None:
    error = UnableToProvideChecksumError("photos/a.jpg", "the file could not be read")

    assert str(error) == (
        "unable to provide a checksum for 'photos/a.jpg': the file could not be read"
    )


def test_it_reads_without_a_reason() -> None:
    error = UnableToProvideChecksumError("photos/a.jpg")

    assert error.reason == ""
    assert str(error) == "unable to provide a checksum for 'photos/a.jpg'"


def test_it_is_a_storage_error_but_not_a_failed_operation() -> None:
    error = UnableToProvideChecksumError("photos/a.jpg")

    assert isinstance(error, StorageError)
    assert not isinstance(error, StorageOperationFailedError)
