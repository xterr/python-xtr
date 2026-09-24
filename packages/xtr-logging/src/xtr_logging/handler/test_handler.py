"""A handler that keeps records in memory, for tests to assert on."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, ClassVar, final

from typing_extensions import override

from xtr_logging.level import Level

from .abstract_processing_handler import AbstractProcessingHandler

if TYPE_CHECKING:
    from collections.abc import Callable

    from xtr_logging.level import LevelLike
    from xtr_logging.log_record import Context, LogRecord

__all__ = ["TestHandler"]


@final
class TestHandler(AbstractProcessingHandler):
    """Records everything it handles, and answers questions about it.

    Put one on a logger under test instead of a file, then ask it what was
    logged::

        handler = TestHandler()
        Logger("app", [handler]).error("payment failed", {"order": 7})

        assert handler.has_record_that_contains("payment", Level.ERROR)

    Records are kept after processing, so a test sees what a real handler
    would have written; :attr:`formatted` holds the rendered text too.
    """

    __test__: ClassVar[bool] = False  # a library class, not a pytest test case

    def __init__(self, level: LevelLike = Level.DEBUG, bubble: bool = True) -> None:
        """Record everything at ``level`` or above."""
        super().__init__(level, bubble)
        self._records: list[LogRecord] = []
        self._formatted: list[str] = []

    @property
    def records(self) -> tuple[LogRecord, ...]:
        """Every record handled, oldest first."""
        return tuple(self._records)

    @property
    def formatted(self) -> tuple[str, ...]:
        """The text each record was rendered to, oldest first."""
        return tuple(self._formatted)

    def clear(self) -> None:
        """Forget every record."""
        self._records.clear()
        self._formatted.clear()

    @override
    def reset(self) -> None:
        """Forget every record and reset the handler's processors."""
        super().reset()
        self.clear()

    def has_records(self, level: LevelLike) -> bool:
        """Whether anything was recorded at exactly ``level``."""
        wanted = Level.parse(level)
        return any(record.level is wanted for record in self._records)

    def has_record(self, message: str, level: LevelLike, context: Context | None = None) -> bool:
        """Whether a record at ``level`` has exactly ``message``, and ``context`` if given."""
        return self.has_record_that_passes(
            lambda record: (
                record.message == message
                and (context is None or dict(record.context) == dict(context))
            ),
            level,
        )

    def has_record_that_contains(self, fragment: str, level: LevelLike) -> bool:
        """Whether a record at ``level`` has a message containing ``fragment``."""
        return self.has_record_that_passes(lambda record: fragment in record.message, level)

    def has_record_that_matches(self, pattern: str | re.Pattern[str], level: LevelLike) -> bool:
        """Whether a record at ``level`` has a message matching ``pattern`` anywhere."""
        compiled = re.compile(pattern)
        return self.has_record_that_passes(
            lambda record: compiled.search(record.message) is not None,
            level,
        )

    def has_record_that_passes(
        self,
        predicate: Callable[[LogRecord], bool],
        level: LevelLike,
    ) -> bool:
        """Whether ``predicate`` holds for some record at exactly ``level``."""
        wanted = Level.parse(level)
        return any(record.level is wanted and predicate(record) for record in self._records)

    @override
    def write(self, record: LogRecord, formatted: str) -> None:
        """Keep ``record`` and its rendering."""
        self._records.append(record)
        self._formatted.append(formatted)
