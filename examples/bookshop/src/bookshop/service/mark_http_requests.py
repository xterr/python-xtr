"""A function processor on the ``http`` channel, declared with ``@as_processor``."""

from __future__ import annotations

from xtr_logging import LogRecord, as_processor

__all__ = ["mark_http_requests"]


@as_processor(channel="http", priority=20)
def mark_http_requests(record: LogRecord, /) -> LogRecord:
    """A function processor: nothing to inject, so the function is the processor."""
    return record.with_extra({"transport": "http/1.1"})
