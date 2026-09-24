"""Every error this library raises.

All of them derive from :class:`ClockError`, so one ``except`` catches
anything a clock can go wrong with, and a narrower one handles a single
cause. Each carries the data a caller needs as typed attributes rather than
forcing a message to be parsed.
"""

from .clock_error import ClockError
from .invalid_modifier_error import InvalidModifierError
from .invalid_timezone_error import InvalidTimezoneError

__all__ = [
    "ClockError",
    "InvalidModifierError",
    "InvalidTimezoneError",
]
