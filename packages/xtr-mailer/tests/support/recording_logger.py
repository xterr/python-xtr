"""A logger that keeps every record, its context rendered into the line."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_logging_contracts import AbstractLogger

if TYPE_CHECKING:
    from xtr_logging_contracts import Context, LevelLike

__all__ = ["RecordingLogger"]


@final
class RecordingLogger(AbstractLogger):
    """Records each message with its placeholders filled from the context.

    Attributes:
        records: Every message logged, in order, placeholders replaced.
    """

    def __init__(self) -> None:
        self.records: list[str] = []

    @override
    def log(self, level: LevelLike, message: str, /, context: Context | None = None) -> None:
        line = message
        for key, value in (context or {}).items():
            line = line.replace(f"{{{key}}}", str(value))
        self.records.append(line)
