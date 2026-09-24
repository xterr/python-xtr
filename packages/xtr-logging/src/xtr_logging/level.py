"""The eight RFC 5424 severities, valued 100 to 600.

The values leave room between them, so a level added later still sorts where
it belongs, and they compare as integers: ``Level.ERROR > Level.WARNING``.
"""

from __future__ import annotations

from enum import IntEnum
from typing import TYPE_CHECKING, Final, TypeAlias

from .exception.invalid_level_error import InvalidLevelError

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ["Level", "LevelLike"]

_LOWEST_RFC5424: Final = 0
_HIGHEST_RFC5424: Final = 7


class Level(IntEnum):
    """A log level, ordered from least to most severe."""

    DEBUG = 100
    INFO = 200
    NOTICE = 250
    WARNING = 300
    ERROR = 400
    CRITICAL = 500
    ALERT = 550
    EMERGENCY = 600

    @classmethod
    def parse(cls, value: LevelLike) -> Level:
        """Read any accepted spelling of a level.

        Accepts a :class:`Level`, its value (``400``), an RFC 5424 severity
        (``3``), or a name in any case (``"error"``, ``"ERROR"``).

        Raises:
            InvalidLevelError: If ``value`` names no level.
        """
        match value:
            case Level():
                return value
            case bool():
                raise InvalidLevelError(value)
            case int():
                if _LOWEST_RFC5424 <= value <= _HIGHEST_RFC5424:
                    return _BY_RFC5424[value]
                if value in _BY_VALUE:
                    return _BY_VALUE[value]
                raise InvalidLevelError(value)
            case str():
                return cls.from_name(value)

    @classmethod
    def from_name(cls, name: str) -> Level:
        """Return the level called ``name``, in any case.

        Raises:
            InvalidLevelError: If no level has that name.
        """
        found = cls.__members__.get(name.upper())
        if found is None:
            raise InvalidLevelError(name)
        return found

    @property
    def lower_name(self) -> str:
        """The name of this level in lower case, as configuration writes it."""
        return self.name.lower()

    @property
    def rfc5424(self) -> int:
        """The RFC 5424 severity: 0 for EMERGENCY through 7 for DEBUG."""
        return _TO_RFC5424[self]

    def includes(self, other: Level) -> bool:
        """Whether a threshold of this level lets ``other`` through."""
        return self <= other

    def is_higher_than(self, other: Level) -> bool:
        """Whether this level is strictly more severe than ``other``."""
        return self > other

    def is_lower_than(self, other: Level) -> bool:
        """Whether this level is strictly less severe than ``other``."""
        return self < other


LevelLike: TypeAlias = Level | int | str
"""Anything :meth:`Level.parse` accepts."""

_TO_RFC5424: Final[Mapping[Level, int]] = {
    Level.EMERGENCY: 0,
    Level.ALERT: 1,
    Level.CRITICAL: 2,
    Level.ERROR: 3,
    Level.WARNING: 4,
    Level.NOTICE: 5,
    Level.INFO: 6,
    Level.DEBUG: 7,
}
_BY_RFC5424: Final[Mapping[int, Level]] = {rfc: level for level, rfc in _TO_RFC5424.items()}
_BY_VALUE: Final[Mapping[int, Level]] = {level.value: level for level in Level}
