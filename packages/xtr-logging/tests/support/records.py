"""Records with fixed, known values."""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING, Final

from xtr_logging import Level, LogRecord

if TYPE_CHECKING:
    from xtr_logging import Context

AT: Final = dt.datetime(2026, 9, 24, 12, 30, 45, 123456, tzinfo=dt.UTC)
"""The time every record made here carries, unless told otherwise."""


def make_record(  # noqa: PLR0913 — a test factory: every field optional, all keyword
    level: Level = Level.INFO,
    message: str = "something happened",
    *,
    channel: str = "app",
    context: Context | None = None,
    extra: Context | None = None,
    at: dt.datetime = AT,
) -> LogRecord:
    """Build a record, defaulting everything a test does not care about."""
    return LogRecord(at, channel, level, message, context or {}, extra or {})
