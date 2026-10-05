"""A checksum of a file could not be produced."""

from __future__ import annotations

from .storage_error import StorageError

__all__ = ["UnableToProvideChecksumError"]


class UnableToProvideChecksumError(StorageError):
    """A file's checksum could neither be read from the backend nor computed.

    Not an operation failure: a checksum is a capability, and a storage that
    cannot get one from the backend falls back to reading the file and
    hashing it. This is what is left when that fails too.

    Attributes:
        location: The path a checksum was wanted for, as the caller gave it.
        reason: Why there is none, empty when nothing more is known.
    """

    location: str
    reason: str

    def __init__(self, location: str, reason: str = "") -> None:
        """Record the path and why no checksum could be produced."""
        self.location = location
        self.reason = reason
        details = f": {reason}" if reason else ""
        super().__init__(f"unable to provide a checksum for {location!r}{details}")
