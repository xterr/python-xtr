from __future__ import annotations

from datetime import UTC, datetime

from xtr_logging import DebugHandler, LogRecord, begin_unit, end_unit
from xtr_logging_contracts import Level

from tests.support.profiling import profiled
from xtr_http_kernel.data_collector.logger_data_collector import LoggerDataCollector


def _record(level: Level, message: str) -> LogRecord:
    return LogRecord(datetime(2026, 1, 1, tzinfo=UTC), "app", level, message, {"isbn": "42"})


def test_the_units_records_and_their_counts_are_kept() -> None:
    handler = DebugHandler()
    collector = LoggerDataCollector(handler)
    begin_unit()
    try:
        for level, message in ((Level.INFO, "a"), (Level.WARNING, "b"), (Level.ERROR, "c")):
            _ = handler.handle(_record(level, message))

        data = collector.late_collect(collector.collect(profiled()), profiled())
    finally:
        end_unit()

    assert data["error_count"] == 1
    assert data["warning_count"] == 1
    assert data["records"] == [
        {
            "time": "2026-01-01T00:00:00+00:00",
            "channel": "app",
            "level": level.name,
            "priority": int(level),
            "message": message,
            "context": {"isbn": {"kind": "str", "type": "str", "value": "42", "truncated": 0}},
        }
        for level, message in ((Level.INFO, "a"), (Level.WARNING, "b"), (Level.ERROR, "c"))
    ]
    assert collector.name == "logger"
