from __future__ import annotations

from xtr_storage.exception import (
    ChecksumAlgorithmNotSupportedError,
    StorageError,
    UnableToProvideChecksumError,
)


def test_it_carries_the_location_and_the_algorithm() -> None:
    error = ChecksumAlgorithmNotSupportedError("photos/a.jpg", "sha256")

    assert error.location == "photos/a.jpg"
    assert error.algorithm == "sha256"


def test_its_message_names_the_algorithm_the_backend_has_not() -> None:
    error = ChecksumAlgorithmNotSupportedError("photos/a.jpg", "sha256")

    assert str(error) == (
        "unable to provide a checksum for 'photos/a.jpg': this backend has no 'sha256' checksum"
    )
    assert error.reason == "this backend has no 'sha256' checksum"


def test_it_is_caught_as_a_missing_checksum() -> None:
    error = ChecksumAlgorithmNotSupportedError("photos/a.jpg", "sha256")

    assert isinstance(error, StorageError)
    assert isinstance(error, UnableToProvideChecksumError)
