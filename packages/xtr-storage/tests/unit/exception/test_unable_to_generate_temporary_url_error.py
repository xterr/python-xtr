from __future__ import annotations

from xtr_storage.exception import (
    StorageError,
    StorageOperationFailedError,
    UnableToGenerateTemporaryUrlError,
)


def test_it_carries_the_location_and_the_reason() -> None:
    error = UnableToGenerateTemporaryUrlError("photos/a.jpg", "this backend does not sign")

    assert error.location == "photos/a.jpg"
    assert error.reason == "this backend does not sign"


def test_its_message_repeats_only_the_location_and_the_reason() -> None:
    error = UnableToGenerateTemporaryUrlError("photos/a.jpg", "this backend does not sign")

    assert str(error) == (
        "unable to generate a temporary url for 'photos/a.jpg': this backend does not sign"
    )


def test_it_reads_without_a_reason() -> None:
    error = UnableToGenerateTemporaryUrlError("photos/a.jpg")

    assert error.reason == ""
    assert str(error) == "unable to generate a temporary url for 'photos/a.jpg'"


def test_it_is_a_storage_error_but_not_a_failed_operation() -> None:
    error = UnableToGenerateTemporaryUrlError("photos/a.jpg")

    assert isinstance(error, StorageError)
    assert not isinstance(error, StorageOperationFailedError)
