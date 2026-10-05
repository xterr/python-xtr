from __future__ import annotations

from xtr_storage.exception import (
    StorageError,
    StorageOperationFailedError,
    UnableToResolveMountError,
)


def test_it_carries_the_location_and_the_reason() -> None:
    error = UnableToResolveMountError("photos/a.jpg", "no mount name was given")

    assert error.location == "photos/a.jpg"
    assert error.reason == "no mount name was given"


def test_its_message_names_the_location_and_the_reason() -> None:
    error = UnableToResolveMountError("photos/a.jpg", "no mount name was given")

    assert str(error) == ("unable to resolve the mount of 'photos/a.jpg': no mount name was given")


def test_it_is_a_storage_error_but_not_a_failed_operation() -> None:
    error = UnableToResolveMountError("archive://a.jpg", "nothing is mounted as 'archive'")

    assert isinstance(error, StorageError)
    assert not isinstance(error, StorageOperationFailedError)
