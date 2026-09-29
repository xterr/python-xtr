"""The contents of a directory could not be listed."""

from __future__ import annotations

from typing import ClassVar

from xtr_storage.operation import Operation

from .storage_operation_failed_error import StorageOperationFailedError

__all__ = ["UnableToListContentsError"]


class UnableToListContentsError(StorageOperationFailedError):
    """Listing a directory failed, at its start or part way through.

    A listing is lazy, so this can surface on any step of the iteration, not
    only on the call that asked for it. :attr:`deep` is carried because a
    shallow listing and a deep one are different requests to the backend and
    fail for different reasons.

    Attributes:
        location: The directory that was listed, as the caller gave it.
        deep: Whether everything below it was being listed too.
    """

    operation: ClassVar[Operation] = Operation.LIST_CONTENTS

    location: str
    deep: bool

    def __init__(self, location: str, deep: bool) -> None:
        """Record the directory and how far the listing reached."""
        self.location = location
        self.deep = deep
        depth = "deep" if deep else "shallow"
        super().__init__(f"unable to list the contents of {location!r} ({depth})")
