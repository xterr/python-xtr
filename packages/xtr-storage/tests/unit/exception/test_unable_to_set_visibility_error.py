from __future__ import annotations

from xtr_storage.exception import (
    StorageError,
    StorageOperationFailedError,
    UnableToSetVisibilityError,
)
from xtr_storage.operation import Operation


def test_it_carries_the_location_and_the_reason() -> None:
    error = UnableToSetVisibilityError("photos/a.jpg", "the bucket owns every policy")

    assert error.location == "photos/a.jpg"
    assert error.reason == "the bucket owns every policy"


def test_its_message_names_the_location_and_the_reason() -> None:
    error = UnableToSetVisibilityError("photos/a.jpg", "the bucket owns every policy")

    assert str(error) == (
        "unable to set the visibility of 'photos/a.jpg': the bucket owns every policy"
    )


def test_it_reads_without_a_reason() -> None:
    error = UnableToSetVisibilityError("photos/a.jpg")

    assert error.reason == ""
    assert str(error) == "unable to set the visibility of 'photos/a.jpg'"


def test_it_is_a_failed_visibility_change() -> None:
    error = UnableToSetVisibilityError("photos/a.jpg")

    assert isinstance(error, StorageError)
    assert isinstance(error, StorageOperationFailedError)
    assert error.operation is Operation.SET_VISIBILITY
