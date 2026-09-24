from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING, final

import pytest
from typing_extensions import override
from xtr_clock import Clock, MockClock

from tests.support.records import AT
from xtr_logging import (
    AbstractHandler,
    EmptyStackError,
    InvalidLevelError,
    Level,
    Logger,
    LogRecord,
    TestHandler,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence


@final
class ExplodingHandler(AbstractHandler):
    @override
    def handle(self, record: LogRecord, /) -> bool:
        raise RuntimeError("handler down")


@final
class EchoingHandler(AbstractHandler):
    """Logs back into its logger for every record — a logging loop."""

    def __init__(self) -> None:
        super().__init__()
        self.logger: Logger | None = None
        self.seen: list[str] = []

    @override
    def handle(self, record: LogRecord, /) -> bool:
        self.seen.append(record.message)
        assert self.logger is not None
        self.logger.info("echo")
        return False


@final
class LifecycleHandler(AbstractHandler):
    def __init__(self) -> None:
        super().__init__()
        self.closed = 0
        self.resets = 0

    @override
    def handle(self, record: LogRecord, /) -> bool:
        return False

    @override
    def close(self) -> None:
        self.closed += 1

    @override
    def reset(self) -> None:
        self.resets += 1


def _stamp(key: str) -> Callable[[LogRecord], LogRecord]:
    def processor(record: LogRecord, /) -> LogRecord:
        order = record.extra.get("order", "")
        return record.with_extra({"order": f"{order}{key}"})

    return processor


def test_a_record_carries_the_channel_level_message_context_and_time() -> None:
    handler = TestHandler()
    logger = Logger("billing", [handler], clock=MockClock(AT))

    logger.error("payment failed", {"order": 7})

    [record] = handler.records
    assert (record.channel, record.level, record.message) == (
        "billing",
        Level.ERROR,
        "payment failed",
    )
    assert dict(record.context) == {"order": 7}
    assert record.datetime == AT


def test_the_first_handler_in_the_stack_is_offered_the_record_first() -> None:
    first, second = TestHandler(bubble=False), TestHandler()
    logger = Logger("app", [first, second])

    logger.info("hello")

    assert len(first.records) == 1
    assert second.records == ()


def test_a_bubbling_handler_lets_the_record_reach_the_next() -> None:
    first, second = TestHandler(), TestHandler()
    logger = Logger("app", [first, second])

    logger.info("hello")

    assert len(first.records) == len(second.records) == 1


def test_a_handler_below_its_level_is_skipped_without_stopping_the_record() -> None:
    errors_only, everything = TestHandler(Level.ERROR, bubble=False), TestHandler()
    logger = Logger("app", [errors_only, everything])

    logger.info("hello")

    assert errors_only.records == ()
    assert len(everything.records) == 1


def test_processors_run_in_order_before_the_handler() -> None:
    handler = TestHandler()
    logger = Logger("app", [handler], [_stamp("a"), _stamp("b")])

    logger.info("hello")

    assert handler.records[0].extra["order"] == "ab"


def test_processors_do_not_run_when_no_handler_would_handle_the_record() -> None:
    calls: list[LogRecord] = []

    def spy(record: LogRecord, /) -> LogRecord:
        calls.append(record)
        return record

    logger = Logger("app", [TestHandler(Level.ERROR)], [spy])

    logger.info("ignored")

    assert calls == []


def test_add_record_reports_whether_any_handler_took_the_record() -> None:
    logger = Logger("app", [TestHandler(Level.ERROR)])

    assert logger.add_record(Level.INFO, "ignored") is False
    assert logger.add_record(Level.ERROR, "kept") is True


def test_add_record_can_backdate_a_record() -> None:
    handler = TestHandler()
    earlier = dt.datetime(2020, 1, 1, tzinfo=dt.UTC)

    _ = Logger("app", [handler]).add_record("warning", "late", datetime=earlier)

    assert handler.records[0].datetime == earlier


def test_log_accepts_any_level_spelling() -> None:
    handler = TestHandler()

    Logger("app", [handler]).log("critical", "down")

    assert handler.has_records(Level.CRITICAL)


def test_log_refuses_an_unknown_level() -> None:
    with pytest.raises(InvalidLevelError):
        Logger("app").log("loud", "x")


def test_a_handler_failure_propagates_by_default() -> None:
    logger = Logger("app", [ExplodingHandler()])

    with pytest.raises(RuntimeError, match="handler down"):
        logger.error("x")


def test_an_exception_handler_receives_the_failure_and_the_record() -> None:
    caught: list[tuple[Exception, LogRecord]] = []
    logger = Logger(
        "app",
        [ExplodingHandler()],
        exception_handler=lambda error, record: caught.append((error, record)),
    )

    logger.error("x")

    [(error, record)] = caught
    assert str(error) == "handler down"
    assert record.message == "x"


def test_a_logging_loop_is_aborted_with_a_warning() -> None:
    echo = EchoingHandler()
    logger = Logger("app", [echo])
    echo.logger = logger

    logger.info("start")

    assert echo.seen[:2] == ["start", "echo"]
    assert echo.seen[2].startswith("A possible infinite logging loop was detected and aborted.")
    assert len(echo.seen) == 3


def test_push_handler_puts_it_on_top() -> None:
    bottom, top = TestHandler(), TestHandler()
    logger = Logger("app", [bottom])

    logger.push_handler(top)

    assert logger.handlers == (top, bottom)


def test_pop_handler_takes_it_off_the_top() -> None:
    bottom, top = TestHandler(), TestHandler()
    logger = Logger("app", [top, bottom])

    assert logger.pop_handler() is top
    assert logger.handlers == (bottom,)


def test_popping_an_empty_handler_stack_is_refused() -> None:
    with pytest.raises(EmptyStackError, match="empty handler stack of logger 'app'"):
        _ = Logger("app").pop_handler()


def test_push_and_pop_processor_work_at_the_front() -> None:
    first, second = _stamp("a"), _stamp("b")
    logger = Logger("app", processors=[first])

    logger.push_processor(second)

    assert logger.processors == (second, first)
    assert logger.pop_processor() is second


def test_popping_an_empty_processor_stack_is_refused() -> None:
    with pytest.raises(EmptyStackError):
        _ = Logger("app").pop_processor()


def test_with_name_shares_handlers_but_not_the_stack() -> None:
    handler = TestHandler()
    app = Logger("app", [handler])

    security = app.with_name("security")
    security.push_handler(TestHandler())
    security.warning("denied")

    assert security.name == "security"
    assert app.handlers == (handler,)
    assert handler.records[0].channel == "security"


def test_is_handling_asks_the_handlers() -> None:
    logger = Logger("app", [TestHandler(Level.WARNING)])

    assert logger.is_handling("warning")
    assert not logger.is_handling(Level.INFO)


def test_close_and_reset_reach_every_handler() -> None:
    handlers: Sequence[LifecycleHandler] = [LifecycleHandler(), LifecycleHandler()]
    logger = Logger("app", handlers)

    logger.close()
    logger.reset()

    assert [(h.closed, h.resets) for h in handlers] == [(1, 1), (1, 1)]


def test_by_default_a_logger_reads_the_clock_in_force() -> None:
    handler = TestHandler()
    logger = Logger("app", [handler])

    with Clock.using(MockClock(AT)):
        logger.info("frozen")

    assert handler.records[0].datetime == AT
