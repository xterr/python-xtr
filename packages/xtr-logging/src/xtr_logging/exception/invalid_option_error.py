"""An option was given a value it cannot work with."""

from __future__ import annotations

from xtr_logging_contracts import LoggingError

__all__ = ["InvalidOptionError"]


class InvalidOptionError(LoggingError, ValueError):
    """An option was given a value it cannot work with.

    Raised where the value is given — a constructor or a configuration entry —
    rather than on the first record that would have exposed it.
    """

    option: str
    value: str
    reason: str

    def __init__(self, option: str, value: str, reason: str) -> None:
        """Record the option, the value it was given, and why that is refused."""
        self.option = option
        self.value = value
        self.reason = reason
        super().__init__(f"{option}={value} is refused: {reason}")
