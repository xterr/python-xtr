from __future__ import annotations

from typing import TYPE_CHECKING, final

import pytest
from typing_extensions import override

from xtr_logging import AbstractLogger, Level

if TYPE_CHECKING:
    from collections.abc import Callable

    from xtr_logging import Context, LevelLike


@final
class RecordingLogger(AbstractLogger):
    def __init__(self) -> None:
        self.calls: list[tuple[LevelLike, str, Context | None]] = []

    @override
    def log(self, level: LevelLike, message: str, /, context: Context | None = None) -> None:
        self.calls.append((level, message, context))


def _method(logger: RecordingLogger, level: Level) -> Callable[[str, Context | None], None]:
    return {
        Level.EMERGENCY: logger.emergency,
        Level.ALERT: logger.alert,
        Level.CRITICAL: logger.critical,
        Level.ERROR: logger.error,
        Level.WARNING: logger.warning,
        Level.NOTICE: logger.notice,
        Level.INFO: logger.info,
        Level.DEBUG: logger.debug,
    }[level]


@pytest.mark.parametrize("level", list(Level))
def test_each_severity_method_logs_at_its_own_level(level: Level) -> None:
    logger = RecordingLogger()

    _method(logger, level)("hello", {"a": 1})

    assert logger.calls == [(level, "hello", {"a": 1})]
