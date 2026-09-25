from __future__ import annotations

import logging
from typing import TYPE_CHECKING, final
from uuid import uuid4

import pytest
from typing_extensions import override
from xtr_logging_contracts import LoggerInterface

from xtr_logging.bridge.stdlib.stdlib_handler import CONTEXT_ATTR
from xtr_logging.bridge.stdlib.stdlib_logger import StdlibLogger

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
    logger = logging.getLogger(f"xtr_adapter_test.{uuid4().hex}")
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


def test_it_logs_through_the_standard_library(stdlib_logger: logging.Logger) -> None:
    collector = _collector_on(stdlib_logger)

    StdlibLogger(stdlib_logger).info("hello")

    [record] = collector.records
    assert record.levelno == logging.INFO
    assert record.getMessage() == "hello"


def test_it_maps_the_library_levels_to_stdlib_numbers(stdlib_logger: logging.Logger) -> None:
    collector = _collector_on(stdlib_logger)
    adapter = StdlibLogger(stdlib_logger)

    adapter.notice("n")
    adapter.critical("c")

    assert [record.levelno for record in collector.records] == [25, 50]


def test_it_carries_context_under_its_own_attribute(stdlib_logger: logging.Logger) -> None:
    collector = _collector_on(stdlib_logger)

    StdlibLogger(stdlib_logger).info("hi", {"user": 1})

    attributes: dict[str, object] = vars(collector.records[0])
    assert attributes[CONTEXT_ATTR] == {"user": 1}


def test_it_passes_an_exception_as_exc_info(stdlib_logger: logging.Logger) -> None:
    collector = _collector_on(stdlib_logger)
    error = ValueError("boom")

    StdlibLogger(stdlib_logger).error("boom", {"exception": error})

    info = collector.records[0].exc_info
    assert info is not None
    assert info[1] is error


def test_it_reports_the_caller_not_the_adapter(stdlib_logger: logging.Logger) -> None:
    collector = _collector_on(stdlib_logger)

    StdlibLogger(stdlib_logger).info("who")

    record = collector.records[0]
    assert record.funcName == "test_it_reports_the_caller_not_the_adapter"
    assert record.filename == "test_stdlib_logger.py"


def test_it_satisfies_the_logger_interface(stdlib_logger: logging.Logger) -> None:
    assert isinstance(StdlibLogger(stdlib_logger), LoggerInterface)


def test_it_accepts_a_logger_name(stdlib_logger: logging.Logger) -> None:
    collector = _collector_on(stdlib_logger)

    StdlibLogger(stdlib_logger.name).info("named")

    assert collector.records[0].getMessage() == "named"
