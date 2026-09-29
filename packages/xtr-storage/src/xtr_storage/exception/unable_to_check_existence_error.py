"""A storage could not say whether something is there."""

from __future__ import annotations

from typing import ClassVar

from xtr_storage.operation import Operation

from .storage_operation_failed_error import StorageOperationFailedError

__all__ = ["UnableToCheckExistenceError"]


class UnableToCheckExistenceError(StorageOperationFailedError):
    """Asking whether a path is there failed.

    Not an answer of "no": the backend could not be asked at all. The two
    subclasses say whether a file or a directory was being looked for, and
    this class catches both.

    Attributes:
        location: The path that was checked, as the caller gave it.
    """

    operation: ClassVar[Operation] = Operation.EXISTENCE_CHECK

    location: str

    def __init__(self, location: str) -> None:
        """Record the path that could not be checked."""
        self.location = location
        super().__init__(f"unable to check whether {location!r} exists")
