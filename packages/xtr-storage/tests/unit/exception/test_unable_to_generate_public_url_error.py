from __future__ import annotations

from xtr_storage.exception import (
    StorageError,
    StorageOperationFailedError,
    UnableToGeneratePublicUrlError,
)


def test_it_carries_the_location_and_the_reason() -> None:
    error = UnableToGeneratePublicUrlError("photos/a.jpg", "no public url generator")

    assert error.location == "photos/a.jpg"
    assert error.reason == "no public url generator"


def test_its_message_names_the_location_and_the_reason() -> None:
    error = UnableToGeneratePublicUrlError("photos/a.jpg", "no public url generator")

    assert str(error) == (
        "unable to generate a public url for 'photos/a.jpg': no public url generator"
    )


def test_it_reads_without_a_reason() -> None:
    error = UnableToGeneratePublicUrlError("photos/a.jpg")

    assert error.reason == ""
    assert str(error) == "unable to generate a public url for 'photos/a.jpg'"


def test_it_is_a_storage_error_but_not_a_failed_operation() -> None:
    error = UnableToGeneratePublicUrlError("photos/a.jpg")

    assert isinstance(error, StorageError)
    assert not isinstance(error, StorageOperationFailedError)
