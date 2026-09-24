from __future__ import annotations

import datetime as dt
import logging
from typing import TYPE_CHECKING, Final

from xtr_logging.bridge.stdlib.stdlib_capture_handler import StdlibCaptureHandler
from xtr_logging.bridge.stdlib.stdlib_handler import BRIDGED_MARKER
from xtr_logging.handler.test_handler import TestHandler
from xtr_logging.level import Level
from xtr_logging.logger import Logger

if TYPE_CHECKING:
    import pytest
from xtr_clock import local_timezone

WHEN: Final = dt.datetime(2020, 1, 2, 3, 4, 5, 678901, tzinfo=dt.UTC)


def test_it_turns_a_stdlib_record_into_a_channel_record() -> None:
    handler = TestHandler()
    capture = StdlibCaptureHandler(Logger("app", [handler]))
    record = logging.LogRecord("ext", logging.WARNING, __file__, 1, "hello %s", ("world",), None)

    capture.emit(record)

    [captured] = handler.records
    assert captured.level is Level.WARNING
    assert captured.message == "hello world"
    assert captured.channel == "app"


def test_it_puts_extra_attributes_into_the_context() -> None:
    handler = TestHandler()
    capture = StdlibCaptureHandler(Logger("app", [handler]))
    record = logging.makeLogRecord(
        {"name": "ext", "levelno": logging.INFO, "msg": "saved", "user_id": 42, "shard": "eu"},
    )

    capture.emit(record)

    assert dict(handler.records[0].context) == {"user_id": 42, "shard": "eu"}


def test_it_leaves_the_context_empty_when_the_record_has_no_extras() -> None:
    handler = TestHandler()
    capture = StdlibCaptureHandler(Logger("app", [handler]))
    record = logging.LogRecord("ext", logging.INFO, __file__, 1, "plain", None, None)

    capture.emit(record)

    assert dict(handler.records[0].context) == {}


def test_it_puts_the_exception_under_the_exception_key() -> None:
    handler = TestHandler()
    capture = StdlibCaptureHandler(Logger("app", [handler]))
    error = ValueError("boom")
    record = logging.LogRecord(
        "ext",
        logging.ERROR,
        __file__,
        1,
        "boom",
        None,
        (type(error), error, error.__traceback__),
    )

    capture.emit(record)

    assert handler.records[0].exception is error


def test_it_keeps_the_original_time_as_an_aware_datetime() -> None:
    handler = TestHandler()
    capture = StdlibCaptureHandler(Logger("app", [handler]))
    record = logging.LogRecord("ext", logging.INFO, __file__, 1, "when", None, None)
    record.created = WHEN.timestamp()

    capture.emit(record)

    captured = handler.records[0]
    assert captured.datetime.tzinfo is not None
    assert abs((captured.datetime - WHEN).total_seconds()) < 0.001


def test_it_reports_the_time_in_the_local_zone_like_a_native_record() -> None:
    handler = TestHandler()
    capture = StdlibCaptureHandler(Logger("app", [handler]))
    record = logging.LogRecord("ext", logging.INFO, __file__, 1, "when", None, None)
    record.created = WHEN.timestamp()

    capture.emit(record)

    assert handler.records[0].datetime.utcoffset() == WHEN.astimezone(local_timezone()).utcoffset()


def test_it_ignores_a_record_this_library_bridged_out() -> None:
    handler = TestHandler()
    capture = StdlibCaptureHandler(Logger("app", [handler]))
    record = logging.makeLogRecord(
        {"name": "ext", "levelno": logging.INFO, "msg": "echo", BRIDGED_MARKER: True},
    )

    capture.emit(record)

    assert handler.records == ()


def test_it_routes_to_a_channel_named_after_the_logger_when_asked() -> None:
    handler = TestHandler()
    capture = StdlibCaptureHandler(Logger("app", [handler]), channel_from_name=True)
    record = logging.LogRecord(
        "sqlalchemy.engine", logging.INFO, __file__, 1, "select 1", None, None
    )

    capture.emit(record)

    assert handler.records[0].channel == "sqlalchemy.engine"


def test_it_reuses_one_channel_per_logger_name(monkeypatch: pytest.MonkeyPatch) -> None:
    base = Logger("app", [TestHandler()])
    capture = StdlibCaptureHandler(base, channel_from_name=True)
    names: list[str] = []
    original = base.with_name

    def counting(name: str) -> Logger:
        names.append(name)
        return original(name)

    monkeypatch.setattr(base, "with_name", counting)
    record = logging.LogRecord("db.pool", logging.INFO, __file__, 1, "x", None, None)

    capture.emit(record)
    capture.emit(record)

    assert names == ["db.pool"]


def test_emit_reports_a_failure_through_handle_error(monkeypatch: pytest.MonkeyPatch) -> None:
    capture = StdlibCaptureHandler(Logger("app", [TestHandler()]))
    failures: list[logging.LogRecord] = []
    monkeypatch.setattr(capture, "handleError", failures.append)
    record = logging.LogRecord("ext", logging.INFO, __file__, 1, "%d", ("not-an-int",), None)

    capture.emit(record)

    assert failures == [record]


def test_a_route_catches_its_logger_and_children_but_not_a_sibling_prefix() -> None:
    handler = TestHandler()
    app = Logger("app", [handler])
    capture = StdlibCaptureHandler(app, routes={"httpx": app.with_name("http")})

    for name in ("httpx", "httpx._client", "httpx2"):
        capture.emit(logging.makeLogRecord({"name": name, "levelno": logging.INFO, "msg": name}))

    assert [(r.message, r.channel) for r in handler.records] == [
        ("httpx", "http"),
        ("httpx._client", "http"),
        ("httpx2", "app"),
    ]


def test_the_most_specific_route_wins() -> None:
    handler = TestHandler()
    app = Logger("app", [handler])
    capture = StdlibCaptureHandler(
        app,
        routes={"sqlalchemy": app.with_name("db"), "sqlalchemy.pool": app.with_name("pool")},
    )

    capture.emit(
        logging.makeLogRecord({"name": "sqlalchemy.pool.impl", "levelno": logging.INFO, "msg": "x"})
    )

    assert handler.records[0].channel == "pool"
