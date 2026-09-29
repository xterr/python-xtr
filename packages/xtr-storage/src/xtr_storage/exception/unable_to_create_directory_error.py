"""A directory could not be created."""

from __future__ import annotations

from typing import ClassVar

from xtr_storage.operation import Operation

from .storage_operation_failed_error import StorageOperationFailedError

__all__ = ["UnableToCreateDirectoryError"]


class UnableToCreateDirectoryError(StorageOperationFailedError):
    """Creating a directory failed.

    Attributes:
        location: The directory that was created, as the caller gave it.
        reason: What the backend said, empty when it said nothing.
    """

    operation: ClassVar[Operation] = Operation.CREATE_DIRECTORY

    location: str
    reason: str

    def __init__(self, location: str, reason: str = "") -> None:
        """Record the directory and why creating it failed."""
        self.location = location
        self.reason = reason
        details = f": {reason}" if reason else ""
        super().__init__(f"unable to create the directory {location!r}{details}")
