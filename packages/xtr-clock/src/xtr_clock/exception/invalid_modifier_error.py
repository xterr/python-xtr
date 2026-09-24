"""A modifier string the grammar cannot read."""

from __future__ import annotations

from .clock_error import ClockError

__all__ = ["InvalidModifierError"]


class InvalidModifierError(ClockError, ValueError):
    """A modifier string the grammar cannot read.

    Raised where the modifier is written rather than silently resolving to
    the current instant, so a typo in ``'+1 dya'`` is a failure and not a
    date that looks plausible.

    Also a :class:`ValueError`, so code that already guards parsing with
    ``except ValueError`` keeps working without learning a new exception.

    Attributes:
        modifier: The string that could not be read.
        reason: What about it could not be read.
    """

    modifier: str
    reason: str

    def __init__(self, modifier: str, reason: str) -> None:
        """Record the modifier that could not be read, and why."""
        self.modifier = modifier
        self.reason = reason
        super().__init__(f"modifier {modifier!r} cannot be read: {reason}")
