"""A file could not be moved."""

from __future__ import annotations

from typing import ClassVar

from xtr_storage.operation import Operation

from .storage_operation_failed_error import StorageOperationFailedError

__all__ = ["UnableToMoveFileError"]


class UnableToMoveFileError(StorageOperationFailedError):
    """Moving a file failed; the source may still be there.

    A move across backends is a copy followed by a delete, so a failure can
    leave the file in both places or in neither. The error names both paths
    for that reason: which one to look at depends on where it stopped.

    Attributes:
        source: The path that was moved from, as the caller gave it.
        destination: The path that was moved to, as the caller gave it.
        reason: What the backend said, empty when it said nothing.
    """

    operation: ClassVar[Operation] = Operation.MOVE

    source: str
    destination: str
    reason: str

    def __init__(self, source: str, destination: str, reason: str = "") -> None:
        """Record both paths and why the move failed."""
        self.source = source
        self.destination = destination
        self.reason = reason
        details = f": {reason}" if reason else ""
        super().__init__(f"unable to move {source!r} to {destination!r}{details}")
