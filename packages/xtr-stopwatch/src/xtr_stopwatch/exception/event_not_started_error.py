"""An event was stopped that is not running."""

from __future__ import annotations

from .stopwatch_error import StopwatchError

__all__ = ["EventNotStartedError"]


class EventNotStartedError(StopwatchError):
    """An event was stopped, or lapped, while it was not running.

    A stop with no start to pair it with has no period to close, so it is
    refused rather than recorded as nothing.

    Attributes:
        name: The event that was not running.
    """

    name: str

    def __init__(self, name: str) -> None:
        """Record the event that was not running."""
        self.name = name
        super().__init__(f'event "{name}" is not started')
