"""An event was asked for that the current section never started."""

from __future__ import annotations

from .stopwatch_error import StopwatchError

__all__ = ["UnknownEventError"]


class UnknownEventError(StopwatchError, LookupError):
    """An event was asked for that the current section never started.

    Also a :class:`LookupError`, as a missing key is.

    Attributes:
        name: The event that is not known.
    """

    name: str

    def __init__(self, name: str) -> None:
        """Record the event that is not known."""
        self.name = name
        super().__init__(f'event "{name}" is not known')
