from __future__ import annotations

import threading
from typing import final

import pytest
from typing_extensions import override
from xtr_logging_contracts import Level

from tests.support.records import make_record
from xtr_logging import AbstractHandler, LogRecord, TestHandler
from xtr_logging.handler.queue_handler import QueueHandler


@final
class Spy(AbstractHandler):
    """Remembers what the worker forwarded to it, and counts closes."""

    def __init__(self) -> None:
        super().__init__()
        self.handled: list[LogRecord] = []
        self.closed = 0

    @override
    def handle(self, record: LogRecord, /) -> bool:
        self.handled.append(record)
        return False

    @override
    def close(self) -> None:
        self.closed += 1


@final
class Boom(AbstractHandler):
    """A handler that always fails, counting how often it was tried."""

    def __init__(self) -> None:
        super().__init__()
        self.attempts = 0

    @override
    def handle(self, record: LogRecord, /) -> bool:
        self.attempts += 1
        raise RuntimeError("boom")


def test_it_forwards_a_record_on_the_worker_thread() -> None:
    spy = Spy()
    handler = QueueHandler(spy)

    _ = handler.handle(make_record(message="hi"))
    handler.close()

    assert [record.message for record in spy.handled] == ["hi"]


def test_flush_waits_for_the_whole_backlog() -> None:
    spy = Spy()
    handler = QueueHandler(spy)

    for message in ("a", "b", "c"):
        _ = handler.handle(make_record(message=message))
    handler.flush()

    assert [record.message for record in spy.handled] == ["a", "b", "c"]
    handler.close()


def test_close_drains_then_closes_the_wrapped_handler() -> None:
    spy = Spy()
    handler = QueueHandler(spy)

    _ = handler.handle(make_record(message="hi"))
    handler.close()

    assert [record.message for record in spy.handled] == ["hi"]
    assert spy.closed == 1


def test_it_is_usable_again_after_close() -> None:
    spy = Spy()
    handler = QueueHandler(spy)
    _ = handler.handle(make_record(message="before"))
    handler.close()

    _ = handler.handle(make_record(message="after"))
    handler.close()

    assert [record.message for record in spy.handled] == ["before", "after"]
    assert spy.closed == 2


def test_a_failing_handler_is_reported_to_on_error() -> None:
    caught: list[tuple[Exception, LogRecord]] = []
    handler = QueueHandler(Boom(), on_error=lambda error, record: caught.append((error, record)))

    _ = handler.handle(make_record(message="doomed"))
    handler.close()

    assert len(caught) == 1
    assert caught[0][1].message == "doomed"


def test_the_worker_survives_a_failing_handler() -> None:
    boom = Boom()
    caught: list[Exception] = []
    handler = QueueHandler(boom, on_error=lambda error, record: caught.append(error))

    _ = handler.handle(make_record(message="one"))
    _ = handler.handle(make_record(message="two"))
    handler.close()

    assert boom.attempts == 2
    assert len(caught) == 2


def test_the_default_on_error_prints_a_traceback(capsys: pytest.CaptureFixture[str]) -> None:
    handler = QueueHandler(Boom())

    _ = handler.handle(make_record())
    handler.close()

    assert "RuntimeError" in capsys.readouterr().err


def test_is_handling_delegates_to_the_wrapped_handler() -> None:
    handler = QueueHandler(TestHandler(Level.ERROR))

    assert handler.is_handling(make_record(Level.ERROR))
    assert not handler.is_handling(make_record(Level.INFO))


def test_handle_lets_the_record_bubble() -> None:
    handler = QueueHandler(Spy())

    result = handler.handle(make_record())
    handler.close()

    assert result is False


class Fatal(BaseException):
    """What a handler raises that is not an ``Exception``."""


@final
class FatalOnce(AbstractHandler):
    """Raises ``Fatal`` on the first record, then remembers the rest."""

    def __init__(self) -> None:
        super().__init__()
        self.handled: list[str] = []

    @override
    def handle(self, record: LogRecord, /) -> bool:
        if not self.handled and record.message == "fatal":
            self.handled.append("")
            raise Fatal
        self.handled.append(record.message)
        return False


def _closes_in_time(handler: QueueHandler) -> bool:
    closing = threading.Thread(target=handler.close, daemon=True)
    closing.start()
    closing.join(timeout=2)
    return not closing.is_alive()


def test_an_error_callback_that_fails_does_not_stop_the_worker() -> None:
    boom = Boom()

    def failing(error: Exception, record: LogRecord) -> None:
        raise ValueError(record.message) from error

    handler = QueueHandler(boom, on_error=failing)
    for message in ("one", "two", "three"):
        _ = handler.handle(make_record(message=message))

    assert _closes_in_time(handler)
    assert boom.attempts == 3


@pytest.mark.filterwarnings("ignore::pytest.PytestUnhandledThreadExceptionWarning")
def test_records_left_by_a_worker_that_died_are_still_handled_on_close() -> None:
    fatal = FatalOnce()
    handler = QueueHandler(fatal)
    for message in ("fatal", "two", "three"):
        _ = handler.handle(make_record(message=message))

    assert _closes_in_time(handler)
    assert fatal.handled[1:] == ["two", "three"]


def test_a_reset_handles_what_is_queued_then_resets_the_wrapped_handler() -> None:
    inner = TestHandler()
    handler = QueueHandler(inner)
    _ = handler.handle(make_record(message="queued"))

    handler.reset()

    assert [record.message for record in inner.records] == []
    handler.close()
