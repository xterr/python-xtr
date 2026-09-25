"""A value names no log level."""

from __future__ import annotations

from .logging_error import LoggingError

__all__ = ["InvalidLevelError"]

_ACCEPTED = "a Level, a level name, a value from 100 to 600, or an RFC 5424 severity from 0 to 7"


class InvalidLevelError(LoggingError, ValueError):
    """A value names no log level.

    Also a :class:`ValueError`, which is what lets a configuration parser
    report the field that held it.
    """

    value: int | str

    def __init__(self, value: int | str) -> None:
        """Record the value that could not be read as a level."""
        self.value = value
        super().__init__(
            f"{value!r} is not a log level; expected {_ACCEPTED}",
        )
