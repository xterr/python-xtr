from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_clock import MockClock

from tests.support.records import AT, make_record
from xtr_logging import AbstractHandler, Level, LogRecord
from xtr_logging.handler.deduplication_handler import DeduplicationHandler

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path


@final
class Spy(AbstractHandler):
    """Remembers every record forwarded to it."""

    def __init__(self) -> None:
        super().__init__()
        self.handled: list[LogRecord] = []

    @override
    def handle(self, record: LogRecord, /) -> bool:
        self.handled.append(record)
        return False

    @override
    def handle_batch(self, records: Sequence[LogRecord], /) -> None:
        self.handled.extend(records)


def test_it_forwards_a_first_time_record(tmp_path: Path) -> None:
    spy = Spy()
    handler = DeduplicationHandler(spy, store=tmp_path / "dedup.log", clock=MockClock(AT))

    _ = handler.handle(make_record(Level.ERROR, "boom"))
    handler.flush()

    assert [record.message for record in spy.handled] == ["boom"]


def test_it_suppresses_a_duplicate_within_the_window(tmp_path: Path) -> None:
    spy = Spy()
    handler = DeduplicationHandler(spy, store=tmp_path / "dedup.log", clock=MockClock(AT))

    _ = handler.handle(make_record(Level.ERROR, "boom"))
    handler.flush()
    _ = handler.handle(make_record(Level.ERROR, "boom"))
    handler.flush()

    assert [record.message for record in spy.handled] == ["boom"]


def test_a_different_message_is_not_suppressed(tmp_path: Path) -> None:
    spy = Spy()
    handler = DeduplicationHandler(spy, store=tmp_path / "dedup.log", clock=MockClock(AT))

    _ = handler.handle(make_record(Level.ERROR, "boom"))
    handler.flush()
    _ = handler.handle(make_record(Level.ERROR, "bang"))
    handler.flush()

    assert [record.message for record in spy.handled] == ["boom", "bang"]


def test_a_record_below_the_dedup_level_always_passes(tmp_path: Path) -> None:
    spy = Spy()
    handler = DeduplicationHandler(spy, store=tmp_path / "dedup.log", clock=MockClock(AT))

    _ = handler.handle(make_record(Level.INFO, "noise"))
    handler.flush()
    _ = handler.handle(make_record(Level.INFO, "noise"))
    handler.flush()

    assert [record.message for record in spy.handled] == ["noise", "noise"]


def test_an_expired_entry_no_longer_suppresses(tmp_path: Path) -> None:
    spy = Spy()
    handler = DeduplicationHandler(spy, store=tmp_path / "dedup.log", time=60, clock=MockClock(AT))
    early = dt.datetime(2026, 9, 24, 12, 0, 0, tzinfo=dt.UTC)
    late = dt.datetime(2026, 9, 24, 13, 0, 0, tzinfo=dt.UTC)

    _ = handler.handle(make_record(Level.ERROR, "boom", at=early))
    handler.flush()
    _ = handler.handle(make_record(Level.ERROR, "boom", at=late))
    handler.flush()

    assert [record.message for record in spy.handled] == ["boom", "boom"]


def test_the_store_records_forwarded_entries(tmp_path: Path) -> None:
    store = tmp_path / "dedup.log"
    handler = DeduplicationHandler(Spy(), store=store, clock=MockClock(AT))

    _ = handler.handle(make_record(Level.ERROR, "boom"))
    handler.flush()

    assert "ERROR:boom" in store.read_text(encoding="utf-8")


def test_bubble_off_stops_the_record(tmp_path: Path) -> None:
    handler = DeduplicationHandler(Spy(), store=tmp_path / "dedup.log", bubble=False)

    assert handler.handle(make_record(Level.ERROR))


def test_flush_on_an_empty_buffer_forwards_nothing(tmp_path: Path) -> None:
    spy = Spy()
    handler = DeduplicationHandler(spy, store=tmp_path / "dedup.log", clock=MockClock(AT))

    handler.flush()

    assert spy.handled == []
