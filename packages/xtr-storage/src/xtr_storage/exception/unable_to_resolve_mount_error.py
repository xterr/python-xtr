"""A location did not name a storage that is mounted."""

from __future__ import annotations

from .storage_error import StorageError

__all__ = ["UnableToResolveMountError"]


class UnableToResolveMountError(StorageError):
    """A location could not be routed to one of the mounted storages.

    Raised before anything is attempted: the location carries no mount name,
    carries an empty one, or names a storage nothing was mounted under. It is
    a mistake in the location, not a failure of the storage behind it, which
    is why it is not one of the operation failures.

    Attributes:
        location: The location that was routed, as the caller gave it.
        reason: What is wrong with it.
    """

    location: str
    reason: str

    def __init__(self, location: str, reason: str) -> None:
        """Record the location and why it routes nowhere."""
        self.location = location
        self.reason = reason
        super().__init__(f"unable to resolve the mount of {location!r}: {reason}")
