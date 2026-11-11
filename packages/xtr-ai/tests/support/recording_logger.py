"""A logger keeping every record, to assert what was logged and what was not."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_logging_contracts import AbstractLogger, Level

if TYPE_CHECKING:
    from xtr_logging_contracts import Context, LevelLike

__all__ = ["RecordingLogger"]


@final
class RecordingLogger(AbstractLogger):
    """Keeps ``(level, message, context)`` for every call."""

    def __init__(self) -> None:
        self.records: list[tuple[Level, str, dict[str, object]]] = []

    @override
    def log(self, level: LevelLike, message: str, /, context: Context | None = None) -> None:
        self.records.append((Level.parse(level), message, dict(context or {})))

    def everything(self) -> str:
        """Every record rendered as one string, to search for what must not be there."""
        return repr(self.records)
