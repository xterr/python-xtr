"""An operation a storage was asked for could not be carried out."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from .storage_error import StorageError

if TYPE_CHECKING:
    from xtr_storage.operation import Operation

__all__ = ["StorageOperationFailedError"]


class StorageOperationFailedError(StorageError):
    """Something a storage was asked to do failed; the operation says what.

    This is the line between "the backend refused this attempt" and every
    other kind of error — a path that is not a path, a feature the backend
    does not have, an argument that makes no sense. Code that retries, or that
    turns a failure into a response, catches this one class and reads
    :attr:`operation` rather than listing every subclass.

    Whatever the backend raised is chained as ``__cause__``.

    Attributes:
        operation: What was being attempted. Every concrete subclass sets it;
            reading it off this class itself raises :class:`AttributeError`,
            which is how a subclass that forgot to set it is found.
    """

    operation: ClassVar[Operation]
