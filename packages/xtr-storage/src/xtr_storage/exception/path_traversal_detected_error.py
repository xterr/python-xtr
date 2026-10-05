"""A path tried to climb out of the storage."""

from __future__ import annotations

from .storage_error import StorageError

__all__ = ["PathTraversalDetectedError"]


class PathTraversalDetectedError(StorageError):
    """A path walked up past the root of the storage.

    Every path is resolved before it reaches a backend, and one whose ``..``
    segments take it above the root is refused there — a storage answers for
    what it holds and for nothing beside it. A storage may also refuse ``..``
    outright, which raises this for any path carrying one.

    Attributes:
        path: The path that was refused, as the caller gave it.
    """

    path: str

    def __init__(self, path: str) -> None:
        """Record the path that climbed out."""
        self.path = path
        super().__init__(f"path traversal detected in {path!r}")
