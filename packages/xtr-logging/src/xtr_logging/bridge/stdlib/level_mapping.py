"""Translating levels between this library's eight and the standard library's five.

:mod:`logging` knows DEBUG, INFO, WARNING, ERROR and CRITICAL. RFC 5424 — and
so this library — also knows NOTICE, ALERT and EMERGENCY. They are slotted in
by number where they belong (NOTICE between INFO and WARNING, ALERT and
EMERGENCY above CRITICAL) so a threshold set on either side keeps its meaning,
and :func:`register_level_names` teaches :mod:`logging` their names so a
formatter prints ``NOTICE`` rather than ``Level 25``.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Final

from xtr_logging.level import Level

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ["from_stdlib", "register_level_names", "to_stdlib"]

_TO_STDLIB: Final[Mapping[Level, int]] = {
    Level.DEBUG: logging.DEBUG,
    Level.INFO: logging.INFO,
    Level.NOTICE: 25,
    Level.WARNING: logging.WARNING,
    Level.ERROR: logging.ERROR,
    Level.CRITICAL: logging.CRITICAL,
    Level.ALERT: 55,
    Level.EMERGENCY: 60,
}

# The extra three, paired with the name logging should print for each. The five
# standard levels already have names, so registering them would only restate
# what logging knows.
_EXTRA_NAMES: Final[Mapping[int, str]] = {
    _TO_STDLIB[Level.NOTICE]: Level.NOTICE.name,
    _TO_STDLIB[Level.ALERT]: Level.ALERT.name,
    _TO_STDLIB[Level.EMERGENCY]: Level.EMERGENCY.name,
}

# Ascending boundaries paired with the level a number below each falls into, so
# a value between two known levels rounds down to the less severe one.
_FROM_STDLIB_BOUNDARIES: Final[tuple[tuple[int, Level], ...]] = (
    (_TO_STDLIB[Level.INFO], Level.DEBUG),
    (_TO_STDLIB[Level.NOTICE], Level.INFO),
    (_TO_STDLIB[Level.WARNING], Level.NOTICE),
    (_TO_STDLIB[Level.ERROR], Level.WARNING),
    (_TO_STDLIB[Level.CRITICAL], Level.ERROR),
    (_TO_STDLIB[Level.ALERT], Level.CRITICAL),
    (_TO_STDLIB[Level.EMERGENCY], Level.ALERT),
)


def to_stdlib(level: Level) -> int:
    """Return the :mod:`logging` number a record at ``level`` should carry."""
    return _TO_STDLIB[level]


def from_stdlib(levelno: int) -> Level:
    """Return the level a :mod:`logging` number falls into.

    A number between two known levels rounds down to the less severe one, the
    way a threshold does: ``logging.WARNING + 1`` is still a warning. Anything
    at or above EMERGENCY's number is an emergency; there is nothing higher.
    """
    for boundary, level in _FROM_STDLIB_BOUNDARIES:
        if levelno < boundary:
            return level
    return Level.EMERGENCY


def register_level_names() -> None:
    """Teach :mod:`logging` the names of NOTICE, ALERT and EMERGENCY.

    Called from the constructors that bridge to :mod:`logging`, never at
    import, so importing this library leaves the global level table untouched
    until something actually crosses the bridge. :func:`logging.addLevelName`
    overwrites, so repeated calls settle on the same three names.
    """
    for number, name in _EXTRA_NAMES.items():
        logging.addLevelName(number, name)
