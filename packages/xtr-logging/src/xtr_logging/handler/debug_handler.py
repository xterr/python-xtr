"""A handler keeping the records of the current unit of work, for a debugging tool to read."""

from __future__ import annotations

from typing import TYPE_CHECKING, final, override

from xtr_logging_contracts import Level

from xtr_logging.log_unit import unit_state

from .abstract_handler import AbstractHandler

if TYPE_CHECKING:
    from xtr_logging_contracts import LevelLike

    from xtr_logging.log_record import LogRecord

__all__ = ["DebugHandler"]


@final
class _Records:
    """One unit's records, appended to in place so a copied context adds to the same list."""

    __slots__ = ("records",)

    def __init__(self) -> None:
        self.records: list[LogRecord] = []


@final
class DebugHandler(AbstractHandler):
    """Keeps every record made during the open unit of work, and nothing outside one.

    A profiler shows the log of one request beside its other panels: this
    handler is how it gets that log. Records are kept per
    :mod:`unit of work <xtr_logging.log_unit>`, so requests served at once
    each keep their own, and the list is let go of when the unit ends — a
    long-running process never accumulates them. Outside a unit nothing is
    kept.

    It always bubbles, whatever ``bubble`` says, because keeping a copy for a
    debugging tool must never take a record away from the handlers that
    write it.
    """

    def __init__(self, level: LevelLike = Level.DEBUG) -> None:
        """Keep the records at ``level`` or above.

        Raises:
            InvalidLevelError: If ``level`` names no level.
        """
        super().__init__(level, bubble=True)

    @override
    def handle(self, record: LogRecord, /) -> bool:
        """Keep ``record`` in the open unit, and let it bubble on."""
        if self.is_handling(record):
            state = unit_state(self, _Records)
            if state is not None:
                state.records.append(record)
        return False

    def get_logs(self) -> tuple[LogRecord, ...]:
        """Return the records of the open unit, oldest first; none outside a unit."""
        state = unit_state(self, _Records)
        return tuple(state.records) if state is not None else ()

    def count_errors(self) -> int:
        """Return how many records of the open unit are at ``ERROR`` or above."""
        return sum(1 for record in self.get_logs() if record.level >= Level.ERROR)
