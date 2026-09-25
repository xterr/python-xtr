"""The errors the contract itself can raise.

Only two live here, because only two can be raised by the contract rather than
by an implementation: :class:`LoggingError`, the root every logging error
derives from — including every one ``xtr-logging`` adds — and
:class:`InvalidLevelError`, which :meth:`Level.parse` raises. Catching
:class:`LoggingError` therefore catches anything logging can go wrong with,
whichever package raised it.
"""

from .invalid_level_error import InvalidLevelError
from .logging_error import LoggingError

__all__ = [
    "InvalidLevelError",
    "LoggingError",
]
