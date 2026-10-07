from __future__ import annotations

import contextlib
import queue
import threading
from typing import TYPE_CHECKING, final

import pytest
from typing_extensions import override
from xtr_logging_contracts import Level

from tests.support.records import make_record
from xtr_logging import AbstractHandler, LogRecord, TestHandler
from xtr_logging.handler.fingers_crossed_handler import FingersCrossedHandler
from xtr_logging.handler.queue_handler import QueueHandler
from xtr_logging.log_unit import begin_unit, end_unit

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Sequence

_TIMEOUT = 2.0
"""Seconds a test waits for a thread that must finish."""

_GRACE = 0.3
"""Seconds a test gives a thread that must stay blocked to show it is not."""


@pytest.fixture(autouse=True)
def _clean_units() -> Iterator[None]:
    """End any unit a synchronous test leaves open in this thread's context."""
    yield
    with contextlib.suppress(BaseException):
        end_unit()


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


@final
class BatchSpy(AbstractHandler):
    """Remembers each batch it is handed, and each single record too."""

    def __init__(self) -> None:
        super().__init__()
        self.batches: list[list[str]] = []

    @override
    def handle(self, record: LogRecord, /) -> bool:
        self.batches.append([record.message])
        return False

    @override
    def handle_batch(self, records: Sequence[LogRecord], /) -> None:
        self.batches.append([record.message for record in records])


def test_queued_records_are_handled_in_the_unit_they_were_logged_from() -> None:
    spy = BatchSpy()
    handler = QueueHandler(FingersCrossedHandler(spy, activation_strategy=Level.ERROR))

    begin_unit()
    _ = handler.handle(make_record(Level.DEBUG, "a-debug"))
    _ = handler.handle(make_record(Level.ERROR, "a-error"))
    end_unit()

    begin_unit()
    _ = handler.handle(make_record(Level.DEBUG, "b-debug"))
    _ = handler.handle(make_record(Level.ERROR, "b-error"))
    end_unit()

    handler.flush()
    handler.close()

    assert spy.batches == [["a-debug", "a-error"], ["b-debug", "b-error"]]


def test_outside_a_unit_queued_records_share_the_wrapped_handlers_buffer() -> None:
    spy = BatchSpy()
    handler = QueueHandler(FingersCrossedHandler(spy, activation_strategy=Level.ERROR))

    _ = handler.handle(make_record(Level.DEBUG, "debug"))
    _ = handler.handle(make_record(Level.ERROR, "error"))
    handler.flush()
    handler.close()

    assert spy.batches == [["debug", "error"]]


def test_it_still_handles_a_record_logged_outside_any_unit() -> None:
    spy = BatchSpy()
    handler = QueueHandler(spy)

    _ = handler.handle(make_record(Level.ERROR, "boom"))
    handler.flush()
    handler.close()

    assert spy.batches == [["boom"]]


@final
class GatedQueue(queue.Queue[object]):
    """Holds the stop marker back until the test opens the gate, and says when it went in."""

    def __init__(self) -> None:
        super().__init__()
        self.stopping = threading.Event()
        self.gate = threading.Event()
        self.stopped = threading.Event()
        self.ahead_of_stop: object | None = None

    @override
    def put(self, item: object, block: bool = True, timeout: float | None = None) -> None:
        if type(item).__name__ != "_Stop":
            super().put(item, block, timeout)
            return
        self.stopping.set()
        _ = self.gate.wait(_TIMEOUT)
        if self.ahead_of_stop is not None:
            super().put(self.ahead_of_stop)
        super().put(item, block, timeout)
        self.stopped.set()


def _gated(handler: QueueHandler, monkeypatch: pytest.MonkeyPatch) -> GatedQueue:
    gated = GatedQueue()
    monkeypatch.setattr(handler, "_queue", gated)
    return gated


def _start(target: Callable[[], object]) -> threading.Thread:
    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    return thread


def test_a_second_close_waits_for_the_first_instead_of_racing_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spy = Spy()
    handler = QueueHandler(spy)
    gated = _gated(handler, monkeypatch)
    _ = handler.handle(make_record(message="hi"))
    first = _start(handler.close)
    assert gated.stopping.wait(_TIMEOUT)

    second = _start(handler.close)
    second.join(_GRACE)
    still_waiting = second.is_alive()
    gated.gate.set()
    first.join(_TIMEOUT)
    second.join(_TIMEOUT)

    assert still_waiting
    assert not first.is_alive()
    assert not second.is_alive()
    assert spy.closed == 2


def test_a_record_logged_during_close_starts_no_worker_until_close_is_done(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spy = Spy()
    handler = QueueHandler(spy)
    gated = _gated(handler, monkeypatch)
    _ = handler.handle(make_record(message="before"))
    closing = _start(handler.close)
    assert gated.stopping.wait(_TIMEOUT)

    logging = _start(lambda: handler.handle(make_record(message="late")))
    logging.join(_GRACE)
    held_back = logging.is_alive()
    gated.gate.set()
    closing.join(_TIMEOUT)
    logging.join(_TIMEOUT)
    handler.flush()

    assert held_back
    assert not closing.is_alive()
    assert [record.message for record in spy.handled] == ["before", "late"]
    assert spy.closed == 1
    handler.close()


@final
class SelfLogging(AbstractHandler):
    """Logs back into the queue handler wrapping it once the stop marker is queued."""

    def __init__(self, stopped: threading.Event) -> None:
        super().__init__()
        self.stopped = stopped
        self.owner: QueueHandler | None = None
        self.handled: list[str] = []
        self.closed_after: list[str] = []

    @override
    def handle(self, record: LogRecord, /) -> bool:
        self.handled.append(record.message)
        if record.message == "trigger" and self.owner is not None:
            _ = self.stopped.wait(_TIMEOUT)
            _ = self.owner.handle(make_record(message="echo"))
        return False

    @override
    def close(self) -> None:
        self.closed_after = list(self.handled)


def test_a_record_the_worker_logs_while_stopping_is_written_before_the_wrapped_handler_closes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gated = GatedQueue()
    inner = SelfLogging(gated.stopped)
    handler = QueueHandler(inner)
    inner.owner = handler
    monkeypatch.setattr(handler, "_queue", gated)
    gated.ahead_of_stop = (make_record(message="trigger"), None)
    gated.gate.set()

    _ = handler.handle(make_record(message="first"))
    assert _closes_in_time(handler)

    assert inner.closed_after == ["first", "trigger", "echo"]
