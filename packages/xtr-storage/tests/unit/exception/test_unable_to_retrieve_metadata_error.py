from __future__ import annotations

from xtr_storage.exception import (
    StorageError,
    StorageOperationFailedError,
    UnableToRetrieveMetadataError,
)
from xtr_storage.operation import Operation


def test_it_carries_the_location_the_kind_and_the_reason() -> None:
    error = UnableToRetrieveMetadataError("photos/a.jpg", "file_size", "no such key")

    assert error.location == "photos/a.jpg"
    assert error.metadata_type == "file_size"
    assert error.reason == "no such key"


def test_its_message_names_the_kind_the_location_and_the_reason() -> None:
    error = UnableToRetrieveMetadataError("photos/a.jpg", "file_size", "no such key")

    assert str(error) == "unable to retrieve the file_size of 'photos/a.jpg': no such key"


def test_it_reads_without_a_reason() -> None:
    error = UnableToRetrieveMetadataError("photos/a.jpg", "mime_type")

    assert error.reason == ""
    assert str(error) == "unable to retrieve the mime_type of 'photos/a.jpg'"


def test_it_is_a_failed_metadata_read() -> None:
    error = UnableToRetrieveMetadataError("photos/a.jpg", "visibility")

    assert isinstance(error, StorageError)
    assert isinstance(error, StorageOperationFailedError)
    assert error.operation is Operation.RETRIEVE_METADATA


def test_last_modified_names_the_kind_it_builds() -> None:
    error = UnableToRetrieveMetadataError.last_modified("photos/a.jpg", "no such key")

    assert error.metadata_type == "last_modified"
    assert error.location == "photos/a.jpg"
    assert str(error) == "unable to retrieve the last_modified of 'photos/a.jpg': no such key"


def test_visibility_names_the_kind_it_builds() -> None:
    error = UnableToRetrieveMetadataError.visibility("photos/a.jpg")

    assert error.metadata_type == "visibility"
    assert str(error) == "unable to retrieve the visibility of 'photos/a.jpg'"


def test_file_size_names_the_kind_it_builds() -> None:
    error = UnableToRetrieveMetadataError.file_size("photos/a.jpg")

    assert error.metadata_type == "file_size"
    assert str(error) == "unable to retrieve the file_size of 'photos/a.jpg'"


def test_mime_type_names_the_kind_it_builds() -> None:
    error = UnableToRetrieveMetadataError.mime_type("photos/a.jpg")

    assert error.metadata_type == "mime_type"
    assert str(error) == "unable to retrieve the mime_type of 'photos/a.jpg'"
