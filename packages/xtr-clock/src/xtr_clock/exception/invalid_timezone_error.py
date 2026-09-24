"""A timezone was named that this system cannot resolve."""

from __future__ import annotations

from .clock_error import ClockError

__all__ = ["InvalidTimezoneError"]


class InvalidTimezoneError(ClockError, ValueError):
    """A timezone was named that this system cannot resolve.

    Also a :class:`ValueError`, so code that already guards a conversion with
    ``except ValueError`` keeps working without learning a new exception.

    Attributes:
        timezone: The name that could not be resolved.
    """

    timezone: str

    def __init__(self, timezone: str) -> None:
        """Record the name that could not be resolved."""
        self.timezone = timezone
        super().__init__(
            f"timezone {timezone!r} is not one this system knows; expected an IANA name "
            f"like 'Europe/Paris', 'UTC', or a fixed offset like '+02:00'",
        )
