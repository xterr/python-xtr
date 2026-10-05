"""No public url could be made for a file."""

from __future__ import annotations

from .storage_error import StorageError

__all__ = ["UnableToGeneratePublicUrlError"]


class UnableToGeneratePublicUrlError(StorageError):
    """A file has no address anyone can fetch it from.

    Usually configuration rather than breakage: nothing told the storage what
    its files are served under, and the backend does not know either. A chain
    of generators raises this once every one of them has declined.

    Attributes:
        location: The path a url was wanted for, as the caller gave it.
        reason: Why there is none, empty when nothing more is known.
    """

    location: str
    reason: str

    def __init__(self, location: str, reason: str = "") -> None:
        """Record the path and why it has no public url."""
        self.location = location
        self.reason = reason
        details = f": {reason}" if reason else ""
        super().__init__(f"unable to generate a public url for {location!r}{details}")
