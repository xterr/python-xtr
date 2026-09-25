"""A logger whose eight severity methods all funnel into ``log``."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from typing_extensions import override

from .level import Level
from .logger_interface import LoggerInterface

if TYPE_CHECKING:
    from .context import Context
    from .level import LevelLike

__all__ = ["AbstractLogger"]


class AbstractLogger(LoggerInterface, ABC):
    """Implements every severity method in terms of :meth:`log`.

    Subclass it and write ``log`` alone.
    """

    @abstractmethod
    @override
    def log(self, level: LevelLike, message: str, /, context: Context | None = None) -> None:
        """Log ``message`` at ``level``."""

    @override
    def emergency(self, message: str, /, context: Context | None = None) -> None:
        """Log at :attr:`Level.EMERGENCY`."""
        self.log(Level.EMERGENCY, message, context)

    @override
    def alert(self, message: str, /, context: Context | None = None) -> None:
        """Log at :attr:`Level.ALERT`."""
        self.log(Level.ALERT, message, context)

    @override
    def critical(self, message: str, /, context: Context | None = None) -> None:
        """Log at :attr:`Level.CRITICAL`."""
        self.log(Level.CRITICAL, message, context)

    @override
    def error(self, message: str, /, context: Context | None = None) -> None:
        """Log at :attr:`Level.ERROR`."""
        self.log(Level.ERROR, message, context)

    @override
    def warning(self, message: str, /, context: Context | None = None) -> None:
        """Log at :attr:`Level.WARNING`."""
        self.log(Level.WARNING, message, context)

    @override
    def notice(self, message: str, /, context: Context | None = None) -> None:
        """Log at :attr:`Level.NOTICE`."""
        self.log(Level.NOTICE, message, context)

    @override
    def info(self, message: str, /, context: Context | None = None) -> None:
        """Log at :attr:`Level.INFO`."""
        self.log(Level.INFO, message, context)

    @override
    def debug(self, message: str, /, context: Context | None = None) -> None:
        """Log at :attr:`Level.DEBUG`."""
        self.log(Level.DEBUG, message, context)
