"""A handler that swallows records."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from xtr_logging.level import Level

from .abstract_handler import AbstractHandler

if TYPE_CHECKING:
    from xtr_logging.level import LevelLike
    from xtr_logging.log_record import LogRecord

__all__ = ["NullHandler"]


@final
class NullHandler(AbstractHandler):
    """Handles records at its level by discarding them, and never lets them bubble.

    Put one on a channel to silence it, or low in a stack to stop what nothing
    above it wanted from reaching anything below.
    """

    def __init__(self, level: LevelLike = Level.DEBUG) -> None:
        """Swallow records at ``level`` or above."""
        super().__init__(level, bubble=False)

    @override
    def handle(self, record: LogRecord, /) -> bool:
        """Discard ``record``; stop it if it is at this handler's level."""
        return self.is_handling(record)
