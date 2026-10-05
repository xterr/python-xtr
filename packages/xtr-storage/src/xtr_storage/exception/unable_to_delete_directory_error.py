"""A directory could not be deleted."""

from __future__ import annotations

from typing import ClassVar

from xtr_storage.operation import Operation

from .storage_operation_failed_error import StorageOperationFailedError

__all__ = ["UnableToDeleteDirectoryError"]


class UnableToDeleteDirectoryError(StorageOperationFailedError):
    """Deleting a directory and everything under it failed.

    The deletion is not atomic anywhere: part of the tree may be gone. A
    caller that must end up with nothing there deletes again rather than
    assuming either outcome.

    Attributes:
        location: The directory that was deleted, as the caller gave it.
        reason: What the backend said, empty when it said nothing.
    """

    operation: ClassVar[Operation] = Operation.DELETE_DIRECTORY

    location: str
    reason: str

    def __init__(self, location: str, reason: str = "") -> None:
        """Record the directory and why deleting it failed."""
        self.location = location
        self.reason = reason
        details = f": {reason}" if reason else ""
        super().__init__(f"unable to delete the directory {location!r}{details}")
