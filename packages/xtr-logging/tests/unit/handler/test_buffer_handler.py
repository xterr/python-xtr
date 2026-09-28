from __future__ import annotations

import contextlib
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, final

import anyio
import anyio.lowlevel
import pytest
from typing_extensions import override
from xtr_logging_contracts import Level

from tests.support.records import make_record
from xtr_logging import AbstractHandler, EmptyStackError, LogRecord
from xtr_logging.handler.buffer_handler import BufferHandler
from xtr_logging.log_unit import begin_unit, end_unit

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence


@pytest.fixture(autouse=True)
def _clean_units() -> Iterator[None]:
    """End any unit a synchronous test leaves open in this thread's context."""
    yield
    with contextlib.suppress(BaseException):
        end_unit()


@final
class Spy(AbstractHandler):
    """Remembers everything it was asked to do, and never forgets it."""

    def __init__(self, level: Level = Level.DEBUG, bubble: bool = True) -> None:
        super().__init__(level, bubble)
        self.handled: list[LogRecord] = []
        self.batches: list[tuple[LogRecord, ...]] = []
        self.closed = 0
        self.resets = 0

    @override
    def handle(self, record: LogRecord, /) -> bool:
        self.handled.append(record)
        return not self.bubble

    @override
    def handle_batch(self, records: Sequence[LogRecord], /) -> None:
        batch = tuple(records)
        self.batches.append(batch)
        self.handled.extend(batch)

    @override
    def close(self) -> None:
        self.closed += 1

    @override
    def reset(self) -> None:
        self.resets += 1


def _stamp(record: LogRecord, /) -> LogRecord:
    return record.with_extra({"stamped": True})


def test_it_holds_records_until_flushed() -> None:
    spy = Spy()
    buffer = BufferHandler(spy)

    _ = buffer.handle(make_record(message="a"))

    assert spy.handled == []


def test_flush_forwards_the_whole_buffer_as_one_batch() -> None:
    spy = Spy()
    buffer = BufferHandler(spy)
    _ = buffer.handle(make_record(message="a"))
    _ = buffer.handle(make_record(message="b"))

    buffer.flush()

    assert [record.message for record in spy.handled] == ["a", "b"]
    assert len(spy.batches) == 1


def test_close_flushes_then_closes_the_wrapped_handler() -> None:
    spy = Spy()
    buffer = BufferHandler(spy)
    _ = buffer.handle(make_record(message="a"))

    buffer.close()

    assert [record.message for record in spy.handled] == ["a"]
    assert spy.closed == 1


def test_a_record_below_the_level_is_not_buffered() -> None:
    spy = Spy()
    buffer = BufferHandler(spy, level=Level.ERROR)

    result = buffer.handle(make_record(Level.INFO))
    buffer.flush()

    assert result is False
    assert spy.handled == []


def test_the_oldest_record_is_dropped_past_the_limit() -> None:
    spy = Spy()
    buffer = BufferHandler(spy, buffer_limit=2)
    for message in ("a", "b", "c"):
        _ = buffer.handle(make_record(message=message))

    buffer.flush()

    assert [record.message for record in spy.handled] == ["b", "c"]


def test_flush_on_overflow_flushes_the_buffer_instead_of_dropping() -> None:
    spy = Spy()
    buffer = BufferHandler(spy, buffer_limit=2, flush_on_overflow=True)

    for message in ("a", "b", "c"):
        _ = buffer.handle(make_record(message=message))

    assert [record.message for record in spy.handled] == ["a", "b"]
    assert len(spy.batches) == 1


def test_clear_discards_the_buffer_without_forwarding() -> None:
    spy = Spy()
    buffer = BufferHandler(spy)
    _ = buffer.handle(make_record(message="a"))

    buffer.clear()
    buffer.flush()

    assert spy.handled == []


def test_reset_flushes_and_resets_the_wrapped_handler() -> None:
    spy = Spy()
    buffer = BufferHandler(spy)
    _ = buffer.handle(make_record(message="a"))

    buffer.reset()

    assert [record.message for record in spy.handled] == ["a"]
    assert spy.resets == 1


def test_bubble_off_stops_the_record() -> None:
    assert BufferHandler(Spy(), bubble=False).handle(make_record())


def test_a_bubbling_buffer_does_not_stop_the_record() -> None:
    assert not BufferHandler(Spy()).handle(make_record())


def test_its_processors_run_before_buffering() -> None:
    spy = Spy()
    buffer = BufferHandler(spy)
    buffer.push_processor(_stamp)

    _ = buffer.handle(make_record())
    buffer.flush()

    assert spy.handled[0].extra["stamped"] is True


def test_popping_with_no_processors_is_refused() -> None:
    with pytest.raises(EmptyStackError, match="BufferHandler"):
        _ = BufferHandler(Spy()).pop_processor()


@final
class LogsWhileHandling(AbstractHandler):
    """Hands a record back to ``into`` the first time it gets a batch, as a flush is under way."""

    def __init__(self) -> None:
        super().__init__()
        self.into: BufferHandler | None = None
        self.batches: list[list[str]] = []

    @override
    def handle(self, record: LogRecord, /) -> bool:
        self.batches.append([record.message])
        return False

    @override
    def handle_batch(self, records: Sequence[LogRecord], /) -> None:
        self.batches.append([record.message for record in records])
        if self.into is not None and len(self.batches) == 1:
            _ = self.into.handle(make_record(message="during"))


def test_a_record_buffered_while_a_flush_forwards_is_kept_for_the_next() -> None:
    inner = LogsWhileHandling()
    buffer = BufferHandler(inner)
    inner.into = buffer
    _ = buffer.handle(make_record(message="before"))

    buffer.flush()
    buffer.flush()

    assert inner.batches == [["before"], ["during"]]


def test_threads_buffering_and_flushing_at_once_lose_no_record() -> None:
    spy = Spy()
    handler = BufferHandler(spy)
    messages = [f"{worker}-{index}" for worker in range(8) for index in range(250)]

    def log(message: str) -> None:
        _ = handler.handle(make_record(message=message))
        if message.endswith("0"):
            handler.flush()

    with ThreadPoolExecutor(8) as pool:
        _ = list(pool.map(log, messages))
    handler.flush()

    assert sorted(record.message for record in spy.handled) == sorted(messages)


def test_end_unit_flushes_the_units_buffer() -> None:
    spy = Spy()
    handler = BufferHandler(spy)
    begin_unit()

    _ = handler.handle(make_record(message="a"))
    _ = handler.handle(make_record(message="b"))
    end_unit()

    assert [record.message for record in spy.handled] == ["a", "b"]
    assert len(spy.batches) == 1


def test_a_units_buffer_stays_empty_for_the_instance() -> None:
    spy = Spy()
    handler = BufferHandler(spy)
    begin_unit()
    _ = handler.handle(make_record(message="in-unit"))
    end_unit()
    spy.handled.clear()

    handler.flush()

    assert spy.handled == []


@pytest.mark.anyio
async def test_two_concurrent_units_flush_only_their_own_records() -> None:
    spy = Spy()
    handler = BufferHandler(spy)
    first_buffered = anyio.Event()

    async def first() -> None:
        begin_unit()
        _ = handler.handle(make_record(message="first"))
        first_buffered.set()
        await anyio.lowlevel.checkpoint()
        handler.flush()
        end_unit()

    async def second() -> None:
        await first_buffered.wait()
        begin_unit()
        _ = handler.handle(make_record(message="second"))
        handler.flush()
        end_unit()

    async with anyio.create_task_group() as task_group:
        _ = task_group.start_soon(first)
        _ = task_group.start_soon(second)

    assert sorted(record.message for record in spy.handled) == ["first", "second"]
    assert all(len(batch) == 1 for batch in spy.batches)
