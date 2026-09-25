from __future__ import annotations

import logging
from typing import TYPE_CHECKING, final
from uuid import uuid4

import pytest
from typing_extensions import override
from xtr_logging_contracts import Level

from tests.support.records import AT, make_record
from xtr_logging.bridge.stdlib.stdlib_handler import (
    BRIDGED_MARKER,
    CHANNEL_ATTR,
    CONTEXT_ATTR,
    EXTRA_ATTR,
    StdlibHandler,
)

if TYPE_CHECKING:
    from collections.abc import Iterator


@final
class _Collector(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    @override
    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


@pytest.fixture
def stdlib_logger() -> Iterator[logging.Logger]:
    logger = logging.getLogger(f"xtr_handler_test.{uuid4().hex}")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    try:
        yield logger
    finally:
        logger.handlers.clear()
        logger.filters.clear()
        logger.setLevel(logging.NOTSET)
        logger.propagate = True


def _collector_on(logger: logging.Logger) -> _Collector:
    collector = _Collector()
    logger.addHandler(collector)
    return collector


def test_it_forwards_a_record_to_the_stdlib_logger(stdlib_logger: logging.Logger) -> None:
    collector = _collector_on(stdlib_logger)

    _ = StdlibHandler(stdlib_logger).handle(make_record(Level.ERROR, "boom"))

    [record] = collector.records
    assert record.levelno == logging.ERROR
    assert record.getMessage() == "boom"
    assert record.name == stdlib_logger.name


def test_it_carries_the_channel_context_and_extra_as_attributes(
    stdlib_logger: logging.Logger,
) -> None:
    collector = _collector_on(stdlib_logger)

    _ = StdlibHandler(stdlib_logger).handle(
        make_record(channel="db", context={"k": "v"}, extra={"uid": "abc"}),
    )

    [record] = collector.records
    attributes: dict[str, object] = vars(record)
    assert attributes[CHANNEL_ATTR] == "db"
    assert attributes[CONTEXT_ATTR] == {"k": "v"}
    assert attributes[EXTRA_ATTR] == {"uid": "abc"}


def test_it_marks_forwarded_records_so_they_are_not_captured_back(
    stdlib_logger: logging.Logger,
) -> None:
    collector = _collector_on(stdlib_logger)

    _ = StdlibHandler(stdlib_logger).handle(make_record())

    attributes: dict[str, object] = vars(collector.records[0])
    assert attributes[BRIDGED_MARKER] is True


def test_it_keeps_the_original_time(stdlib_logger: logging.Logger) -> None:
    collector = _collector_on(stdlib_logger)

    _ = StdlibHandler(stdlib_logger).handle(make_record())

    record = collector.records[0]
    assert record.created == AT.timestamp()
    assert record.msecs == AT.microsecond / 1000


def test_it_passes_an_exception_as_exc_info(stdlib_logger: logging.Logger) -> None:
    collector = _collector_on(stdlib_logger)
    error = ValueError("boom")

    _ = StdlibHandler(stdlib_logger).handle(
        make_record(Level.ERROR, context={"exception": error}),
    )

    info = collector.records[0].exc_info
    assert info is not None
    assert info[1] is error


def test_it_does_not_forward_when_the_stdlib_logger_is_disabled(
    stdlib_logger: logging.Logger,
) -> None:
    collector = _collector_on(stdlib_logger)
    stdlib_logger.setLevel(logging.CRITICAL)

    handled = StdlibHandler(stdlib_logger).handle(make_record(Level.INFO))

    assert collector.records == []
    assert handled is False


def test_it_returns_not_bubble_only_when_it_forwards(stdlib_logger: logging.Logger) -> None:
    _ = _collector_on(stdlib_logger)

    assert StdlibHandler(stdlib_logger, bubble=False).handle(make_record()) is True
    assert StdlibHandler(stdlib_logger).handle(make_record()) is False


def test_a_record_below_the_handler_level_is_not_forwarded(stdlib_logger: logging.Logger) -> None:
    collector = _collector_on(stdlib_logger)

    handled = StdlibHandler(stdlib_logger, level=Level.ERROR).handle(make_record(Level.INFO))

    assert collector.records == []
    assert handled is False


def test_it_accepts_a_logger_name(stdlib_logger: logging.Logger) -> None:
    collector = _collector_on(stdlib_logger)

    _ = StdlibHandler(stdlib_logger.name).handle(make_record(Level.WARNING, "named"))

    assert collector.records[0].getMessage() == "named"
