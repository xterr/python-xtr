"""A file could not be copied."""

from __future__ import annotations

from typing import ClassVar

from xtr_storage.operation import Operation

from .storage_operation_failed_error import StorageOperationFailedError

__all__ = ["UnableToCopyFileError"]


class UnableToCopyFileError(StorageOperationFailedError):
    """Copying a file failed; the destination may be half-written.

    A copy across backends is a read streamed into a write, so a failure part
    way through leaves whatever reached the destination. The source is never
    touched.

    Attributes:
        source: The path that was copied from, as the caller gave it.
        destination: The path that was copied to, as the caller gave it.
        reason: What the backend said, empty when it said nothing.
    """

    operation: ClassVar[Operation] = Operation.COPY

    source: str
    destination: str
    reason: str

    def __init__(self, source: str, destination: str, reason: str = "") -> None:
        """Record both paths and why the copy failed."""
        self.source = source
        self.destination = destination
        self.reason = reason
        details = f": {reason}" if reason else ""
        super().__init__(f"unable to copy {source!r} to {destination!r}{details}")
