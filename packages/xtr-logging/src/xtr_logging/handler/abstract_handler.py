"""What every handler shares: a minimum level, and whether records bubble past it."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from typing_extensions import override

from xtr_logging.level import Level
from xtr_logging.resettable_interface import ResettableInterface

from .handler_interface import HandlerInterface

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_logging.level import LevelLike
    from xtr_logging.log_record import LogRecord

__all__ = ["AbstractHandler"]


class AbstractHandler(HandlerInterface, ResettableInterface, ABC):
    """A handler with a minimum level and a bubble flag.

    Handles records at ``level`` or above. With ``bubble`` on — the default —
    a record it handles still reaches the handlers after it; turned off, the
    record stops here.
    """

    def __init__(self, level: LevelLike = Level.DEBUG, bubble: bool = True) -> None:
        """Handle records at ``level`` or above, letting them bubble on if ``bubble``.

        Raises:
            InvalidLevelError: If ``level`` names no level.
        """
        self._level: Level = Level.parse(level)
        self._bubble: bool = bubble

    @property
    def level(self) -> Level:
        """The least severe level this handler handles."""
        return self._level

    @property
    def bubble(self) -> bool:
        """Whether a handled record goes on to the next handler."""
        return self._bubble

    def set_level(self, level: LevelLike) -> None:
        """Handle records at ``level`` or above from now on.

        Raises:
            InvalidLevelError: If ``level`` names no level.
        """
        self._level = Level.parse(level)

    @override
    def is_handling(self, record: LogRecord, /) -> bool:
        """Whether ``record`` is at this handler's level or above."""
        return record.level >= self._level

    @abstractmethod
    @override
    def handle(self, record: LogRecord, /) -> bool:
        """Handle ``record``; return ``True`` to stop it bubbling."""

    @override
    def handle_batch(self, records: Sequence[LogRecord], /) -> None:
        """Handle each record in turn."""
        for record in records:
            _ = self.handle(record)

    @override
    def close(self) -> None:
        """Release nothing; handlers holding resources override this."""

    @override
    def reset(self) -> None:
        """Forget nothing; handlers holding per-unit-of-work state override this."""
