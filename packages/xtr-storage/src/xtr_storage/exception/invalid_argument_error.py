"""A storage, an adapter or a generator was given an argument it cannot work with."""

from __future__ import annotations

from .storage_error import StorageError

__all__ = ["InvalidArgumentError"]


class InvalidArgumentError(StorageError, ValueError):
    """A storage, an adapter or a generator was given an argument it cannot use.

    Raised where the argument is given — an empty prefix, a checksum algorithm
    this machine does not have, an expiry without a time zone — rather than on
    the first attempt to reach a backend.

    Also a :class:`ValueError`, so code that already guards its configuration
    with ``except ValueError`` keeps working without learning a new exception.

    Attributes:
        reason: What is wrong with the argument.
    """

    reason: str

    def __init__(self, reason: str) -> None:
        """Record what is wrong with the argument."""
        self.reason = reason
        super().__init__(reason)
