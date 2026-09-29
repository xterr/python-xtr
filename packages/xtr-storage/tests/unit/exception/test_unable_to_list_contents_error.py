from __future__ import annotations

from xtr_storage.exception import (
    StorageError,
    StorageOperationFailedError,
    UnableToListContentsError,
)
from xtr_storage.operation import Operation


def test_it_carries_the_location_and_how_far_it_reached() -> None:
    error = UnableToListContentsError("photos", deep=True)

    assert error.location == "photos"
    assert error.deep is True


def test_a_deep_listing_says_so_in_its_message() -> None:
    error = UnableToListContentsError("photos", deep=True)

    assert str(error) == "unable to list the contents of 'photos' (deep)"


def test_a_shallow_listing_says_so_in_its_message() -> None:
    error = UnableToListContentsError("photos", deep=False)

    assert error.deep is False
    assert str(error) == "unable to list the contents of 'photos' (shallow)"


def test_it_is_a_failed_listing() -> None:
    error = UnableToListContentsError("photos", deep=False)

    assert isinstance(error, StorageError)
    assert isinstance(error, StorageOperationFailedError)
    assert error.operation is Operation.LIST_CONTENTS
