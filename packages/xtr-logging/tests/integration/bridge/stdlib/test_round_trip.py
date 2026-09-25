from __future__ import annotations

import logging
from typing import TYPE_CHECKING, final
from uuid import uuid4

import pytest
from typing_extensions import override
from xtr_logging_contracts import Level

from xtr_logging.bridge.stdlib.stdlib_capture import StdlibCapture
from xtr_logging.bridge.stdlib.stdlib_handler import StdlibHandler
from xtr_logging.handler.test_handler import TestHandler
from xtr_logging.logger import Logger

pytestmark = pytest.mark.usefixtures("stdlib_logging")

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
def stdlib_name() -> Iterator[str]:
    name = f"sqlalchemy.engine.{uuid4().hex}"
    yield name
    logger = logging.getLogger(name)
    logger.handlers.clear()
    logger.filters.clear()
    logger.setLevel(logging.NOTSET)
    logger.propagate = True


def test_a_third_party_stdlib_record_is_captured_into_a_channel(stdlib_name: str) -> None:
    handler = TestHandler()
    stdlib_logger = logging.getLogger(stdlib_name)
    stdlib_logger.propagate = False

    with StdlibCapture(Logger("app", [handler]), levels={stdlib_name: "info"}):
        stdlib_logger.info("connection pool opened")

    assert handler.has_record_that_contains("connection pool opened", Level.INFO)


def test_a_channel_record_reaches_a_standard_library_handler(stdlib_name: str) -> None:
    stdlib_logger = logging.getLogger(stdlib_name)
    stdlib_logger.setLevel(logging.DEBUG)
    stdlib_logger.propagate = False
    collector = _Collector()
    stdlib_logger.addHandler(collector)
    channel = Logger("app", [StdlibHandler(stdlib_logger)])

    channel.error("disk failing")

    [record] = collector.records
    assert record.levelno == logging.ERROR
    assert record.getMessage() == "disk failing"


def test_both_directions_installed_at_once_do_not_loop(stdlib_name: str) -> None:
    stdlib_logger = logging.getLogger(stdlib_name)
    stdlib_logger.setLevel(logging.DEBUG)
    stdlib_logger.propagate = False
    seen = TestHandler()
    channel = Logger("app", [seen, StdlibHandler(stdlib_logger)])

    with StdlibCapture(channel, levels={stdlib_name: "debug"}):
        channel.info("from the channel")
        stdlib_logger.info("from the standard library")

    assert seen.has_record_that_contains("from the channel", Level.INFO)
    assert seen.has_record_that_contains("from the standard library", Level.INFO)
