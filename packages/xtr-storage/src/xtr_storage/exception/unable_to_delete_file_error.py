"""A file could not be deleted."""

from __future__ import annotations

from typing import ClassVar

from xtr_storage.operation import Operation

from .storage_operation_failed_error import StorageOperationFailedError

__all__ = ["UnableToDeleteFileError"]


class UnableToDeleteFileError(StorageOperationFailedError):
    """Deleting a file failed while the file was there.

    Deleting what is not there is not a failure: a delete asks for the file to
    be gone, and it is. This is raised only when the backend refused.

    Attributes:
        location: The path that was deleted, as the caller gave it.
        reason: What the backend said, empty when it said nothing.
    """

    operation: ClassVar[Operation] = Operation.DELETE

    location: str
    reason: str

    def __init__(self, location: str, reason: str = "") -> None:
        """Record the path and why deleting it failed."""
        self.location = location
        self.reason = reason
        details = f": {reason}" if reason else ""
        super().__init__(f"unable to delete the file {location!r}{details}")
