from __future__ import annotations

from xtr_storage.exception import (
    FeatureNotSupportedError,
    StorageError,
    StorageOperationFailedError,
)
from xtr_storage.feature import Feature


def test_it_carries_the_feature_and_the_adapter() -> None:
    error = FeatureNotSupportedError(Feature.VISIBILITY, "GcsAdapter")

    assert error.feature is Feature.VISIBILITY
    assert error.adapter == "GcsAdapter"


def test_its_message_names_both() -> None:
    error = FeatureNotSupportedError(Feature.VISIBILITY, "GcsAdapter")

    assert str(error) == "GcsAdapter does not support visibility"


def test_it_is_also_a_not_implemented_error() -> None:
    error = FeatureNotSupportedError(Feature.TEMPORARY_URL, "LocalAdapter")

    assert isinstance(error, StorageError)
    assert isinstance(error, NotImplementedError)


def test_it_is_not_a_failed_operation() -> None:
    error = FeatureNotSupportedError(Feature.CHECKSUM, "InMemoryAdapter")

    assert not isinstance(error, StorageOperationFailedError)
