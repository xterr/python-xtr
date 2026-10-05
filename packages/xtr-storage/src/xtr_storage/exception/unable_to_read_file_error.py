"""A file could not be read."""

from __future__ import annotations

from typing import ClassVar

from xtr_storage.operation import Operation

from .storage_operation_failed_error import StorageOperationFailedError

__all__ = ["UnableToReadFileError"]


class UnableToReadFileError(StorageOperationFailedError):
    """A file could not be read: it is not there, or the backend refused.

    Missing and unreadable are one error on purpose. An object store answers
    both the same way, so a caller that wants to know whether a file is there
    asks ``file_exists`` rather than reading it and reading the failure.

    Attributes:
        location: The path that was read, as the caller gave it.
        reason: What the backend said, empty when it said nothing.
    """

    operation: ClassVar[Operation] = Operation.READ

    location: str
    reason: str

    def __init__(self, location: str, reason: str = "") -> None:
        """Record the path and why reading it failed."""
        self.location = location
        self.reason = reason
        details = f": {reason}" if reason else ""
        super().__init__(f"unable to read the file {location!r}{details}")
