"""Trigger on the first record at or above a level — the common case."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_logging_contracts import Level

from .activation_strategy_interface import ActivationStrategyInterface

if TYPE_CHECKING:
    from xtr_logging_contracts import LevelLike

    from xtr_logging.log_record import LogRecord

__all__ = ["ErrorLevelActivationStrategy"]


@final
class ErrorLevelActivationStrategy(ActivationStrategyInterface):
    """Releases the buffer once a record reaches ``action_level``.

    The default a fingers-crossed handler falls back to: keep the whole
    request's log only when an error — or whatever level was named — actually
    occurred.
    """

    __slots__ = ("_action_level",)

    def __init__(self, action_level: LevelLike) -> None:
        """Activate on records at ``action_level`` or above.

        Raises:
            InvalidLevelError: If ``action_level`` names no level.
        """
        self._action_level = Level.parse(action_level)

    @override
    def is_handler_activated(self, record: LogRecord, /) -> bool:
        """Whether ``record`` is at ``action_level`` or above."""
        return record.level >= self._action_level
