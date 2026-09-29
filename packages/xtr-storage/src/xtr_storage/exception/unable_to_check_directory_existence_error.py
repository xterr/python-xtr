"""A storage could not say whether a directory is there."""

from __future__ import annotations

from typing import ClassVar

from xtr_storage.operation import Operation

from .unable_to_check_existence_error import UnableToCheckExistenceError

__all__ = ["UnableToCheckDirectoryExistenceError"]


class UnableToCheckDirectoryExistenceError(UnableToCheckExistenceError):
    """Asking whether a directory is there failed.

    The class name is what tells a reader a directory was being looked for;
    the message stays the same as its parent's so the two read alike in a log.

    Attributes:
        location: The path that was checked, as the caller gave it.
    """

    operation: ClassVar[Operation] = Operation.DIRECTORY_EXISTS
