"""A visibility was asked for that this library does not know."""

from __future__ import annotations

from .storage_error import StorageError

__all__ = ["InvalidVisibilityError"]


class InvalidVisibilityError(StorageError, ValueError):
    """A value was handed in as a visibility and is not one.

    Visibility travels as a plain string through configuration files and
    request bodies, so it is parsed on the way in and anything unknown is
    refused there — before an adapter turns it into permissions or an access
    policy it cannot take back.

    Also a :class:`ValueError`, so code already guarding its configuration
    with ``except ValueError`` keeps working.

    Attributes:
        visibility: The value that was refused.
    """

    visibility: str

    def __init__(self, visibility: str) -> None:
        """Record the value that is not a visibility."""
        self.visibility = visibility
        super().__init__(f"{visibility!r} is not a known visibility")
