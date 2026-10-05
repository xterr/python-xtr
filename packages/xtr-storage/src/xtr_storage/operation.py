"""What a storage was doing when it failed."""

from __future__ import annotations

from enum import StrEnum

__all__ = ["Operation"]


class Operation(StrEnum):
    """The operation an :class:`~xtr_storage.exception.StorageOperationFailedError` was in.

    Every failed operation carries one of these as a class attribute, so code
    catching the one base error can still branch on what was attempted instead
    of listing a dozen exception types. The values are stable, lower-case
    names, fit to log or to put in a response body.
    """

    WRITE = "write"
    READ = "read"
    DELETE = "delete"
    DELETE_DIRECTORY = "delete_directory"
    CREATE_DIRECTORY = "create_directory"
    MOVE = "move"
    COPY = "copy"
    RETRIEVE_METADATA = "retrieve_metadata"
    SET_VISIBILITY = "set_visibility"
    LIST_CONTENTS = "list_contents"
    FILE_EXISTS = "file_exists"
    DIRECTORY_EXISTS = "directory_exists"
    EXISTENCE_CHECK = "existence_check"
