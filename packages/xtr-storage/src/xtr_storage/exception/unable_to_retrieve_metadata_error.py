"""Something a storage knows about a file could not be read."""

from __future__ import annotations

from typing import ClassVar, Self

from xtr_storage.operation import Operation

from .storage_operation_failed_error import StorageOperationFailedError

__all__ = ["UnableToRetrieveMetadataError"]


class UnableToRetrieveMetadataError(StorageOperationFailedError):
    """A file's size, type, visibility or last write could not be read.

    One error for all four, with :attr:`metadata_type` saying which: they fail
    together — a missing file has none of them — and a caller asking for two
    would otherwise catch two exception types for one cause. The classmethods
    build each kind, so no call site has to spell the name.

    Attributes:
        location: The path the metadata was read for, as the caller gave it.
        metadata_type: Which piece was asked for — ``last_modified``,
            ``visibility``, ``file_size`` or ``mime_type``.
        reason: What the backend said, empty when it said nothing.
    """

    operation: ClassVar[Operation] = Operation.RETRIEVE_METADATA

    location: str
    metadata_type: str
    reason: str

    def __init__(self, location: str, metadata_type: str, reason: str = "") -> None:
        """Record the path, what was asked for, and why it could not be read."""
        self.location = location
        self.metadata_type = metadata_type
        self.reason = reason
        details = f": {reason}" if reason else ""
        super().__init__(f"unable to retrieve the {metadata_type} of {location!r}{details}")

    @classmethod
    def last_modified(cls, location: str, reason: str = "") -> Self:
        """Build the failure for the moment a file was last written."""
        return cls(location, "last_modified", reason)

    @classmethod
    def visibility(cls, location: str, reason: str = "") -> Self:
        """Build the failure for who may read a file."""
        return cls(location, "visibility", reason)

    @classmethod
    def file_size(cls, location: str, reason: str = "") -> Self:
        """Build the failure for how many bytes a file holds."""
        return cls(location, "file_size", reason)

    @classmethod
    def mime_type(cls, location: str, reason: str = "") -> Self:
        """Build the failure for what kind of content a file holds."""
        return cls(location, "mime_type", reason)
