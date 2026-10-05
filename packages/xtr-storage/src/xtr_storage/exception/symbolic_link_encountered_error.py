"""A symbolic link turned up where only files and directories were expected."""

from __future__ import annotations

from .storage_error import StorageError

__all__ = ["SymbolicLinkEncounteredError"]


class SymbolicLinkEncounteredError(StorageError):
    """A listing ran into a symbolic link and was told to refuse them.

    A link can point anywhere, including outside the storage, so following one
    would quietly hand out what the storage does not hold. An adapter that
    meets one either skips it or raises this, depending on how it was built.

    Attributes:
        location: The link that was met, as the storage names it.
    """

    location: str

    def __init__(self, location: str) -> None:
        """Record the link that was refused."""
        self.location = location
        super().__init__(f"unsupported symbolic link encountered at {location!r}")
