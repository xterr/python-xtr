from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from tests.support.records import make_record
from xtr_logging import AbstractHandler, Level, LogRecord, TestHandler
from xtr_logging.handler.queue_handler import QueueHandler

if TYPE_CHECKING:
    import pytest


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
