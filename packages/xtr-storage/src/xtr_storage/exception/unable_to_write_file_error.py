"""A file could not be written."""

from __future__ import annotations

from typing import ClassVar

from xtr_storage.operation import Operation

from .storage_operation_failed_error import StorageOperationFailedError

__all__ = ["UnableToWriteFileError"]


class UnableToWriteFileError(StorageOperationFailedError):
    """Writing a file failed, whether or not anything was written.

    A backend that fails midway may leave a partial object behind; the error
    says where to look, not what survived, because only the backend knows.

    Attributes:
        location: The path that was written to, as the caller gave it.
        reason: What the backend said, empty when it said nothing.
    """

    operation: ClassVar[Operation] = Operation.WRITE

    location: str
    reason: str

    def __init__(self, location: str, reason: str = "") -> None:
        """Record the path and why writing it failed."""
        self.location = location
        self.reason = reason
        details = f": {reason}" if reason else ""
        super().__init__(f"unable to write the file {location!r}{details}")
