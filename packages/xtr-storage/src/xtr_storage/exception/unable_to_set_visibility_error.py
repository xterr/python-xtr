"""The visibility of a file or directory could not be changed."""

from __future__ import annotations

from typing import ClassVar

from xtr_storage.operation import Operation

from .storage_operation_failed_error import StorageOperationFailedError

__all__ = ["UnableToSetVisibilityError"]


class UnableToSetVisibilityError(StorageOperationFailedError):
    """Changing who may read a file or a directory failed.

    A backend that has no notion of visibility at all raises
    :class:`~xtr_storage.exception.FeatureNotSupportedError` instead: this one
    means the backend has it and the attempt failed.

    Attributes:
        location: The path whose visibility was set, as the caller gave it.
        reason: What the backend said, empty when it said nothing.
    """

    operation: ClassVar[Operation] = Operation.SET_VISIBILITY

    location: str
    reason: str

    def __init__(self, location: str, reason: str = "") -> None:
        """Record the path and why its visibility could not be set."""
        self.location = location
        self.reason = reason
        details = f": {reason}" if reason else ""
        super().__init__(f"unable to set the visibility of {location!r}{details}")
