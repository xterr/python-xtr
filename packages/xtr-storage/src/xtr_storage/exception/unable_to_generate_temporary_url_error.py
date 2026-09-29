"""No expiring url could be made for a file."""

from __future__ import annotations

from .storage_error import StorageError

__all__ = ["UnableToGenerateTemporaryUrlError"]


class UnableToGenerateTemporaryUrlError(StorageError):
    """A file has no address that lets the bearer fetch it until a deadline.

    A backend signs such a url with the credentials it holds, so this covers
    both "this backend does not sign" and "signing failed". The message never
    repeats what was signed with.

    Attributes:
        location: The path a url was wanted for, as the caller gave it.
        reason: Why there is none, empty when nothing more is known.
    """

    location: str
    reason: str

    def __init__(self, location: str, reason: str = "") -> None:
        """Record the path and why it has no temporary url."""
        self.location = location
        self.reason = reason
        details = f": {reason}" if reason else ""
        super().__init__(f"unable to generate a temporary url for {location!r}{details}")
