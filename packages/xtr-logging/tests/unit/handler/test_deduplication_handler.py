from __future__ import annotations

import contextlib
import datetime as dt
import os
import stat
import tempfile
from typing import TYPE_CHECKING, final

import pytest
from typing_extensions import override
from xtr_clock import MockClock
from xtr_logging_contracts import Level

from tests.support.records import AT, make_record
from xtr_logging import AbstractHandler, LogRecord
from xtr_logging.handler.deduplication_handler import DeduplicationHandler
from xtr_logging.log_unit import begin_unit, end_unit

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence
    from pathlib import Path


@pytest.fixture(autouse=True)
def _clean_units() -> Iterator[None]:
    """End any unit a synchronous test leaves open in this thread's context."""
    yield
    with contextlib.suppress(BaseException):
        end_unit()


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


@pytest.fixture
def temporary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Stand in for the system's temporary directory, where the default store goes."""
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    return tmp_path


def _flush_twice(handler: DeduplicationHandler) -> None:
    for _ in range(2):
        _ = handler.handle(make_record(Level.ERROR, "boom"))
        handler.flush()


def test_the_default_store_is_private_to_this_user(temporary: Path) -> None:
    spy = Spy()
    handler = DeduplicationHandler(spy, clock=MockClock(AT))

    _flush_twice(handler)

    (directory,) = [path for path in temporary.iterdir() if path.is_dir()]
    assert stat.S_IMODE(directory.stat().st_mode) == 0o700
    assert [record.message for record in spy.handled] == ["boom"]


@pytest.mark.skipif(not hasattr(os, "getuid"), reason="file ownership is POSIX")
def test_a_default_store_directory_of_another_user_is_not_used(
    temporary: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spy = Spy()
    handler = DeduplicationHandler(spy, clock=MockClock(AT))
    monkeypatch.setattr(os, "getuid", lambda: temporary.stat().st_uid + 1)

    _flush_twice(handler)

    assert [record.message for record in spy.handled] == ["boom", "boom"]


def test_two_handlers_wrapping_differently_set_handlers_do_not_suppress_each_other(
    temporary: Path,
) -> None:
    first, second = Spy(), Spy()
    second.set_level(Level.WARNING)
    for spy in (first, second):
        handler = DeduplicationHandler(spy, clock=MockClock(AT))
        _ = handler.handle(make_record(Level.ERROR, "boom"))
        handler.flush()

    assert [len(spy.handled) for spy in (first, second)] == [1, 1]
    assert any(temporary.iterdir())


def test_a_buffer_limit_keeps_only_the_newest_records(tmp_path: Path) -> None:
    spy = Spy()
    handler = DeduplicationHandler(spy, store=tmp_path / "dedup.log", buffer_limit=2)

    for message in ("one", "two", "three"):
        _ = handler.handle(make_record(Level.INFO, message))
    handler.flush()

    assert [record.message for record in spy.handled] == ["two", "three"]


def test_end_unit_flushes_the_units_buffer(tmp_path: Path) -> None:
    spy = Spy()
    handler = DeduplicationHandler(spy, store=tmp_path / "dedup.log", clock=MockClock(AT))
    begin_unit()

    _ = handler.handle(make_record(Level.ERROR, "boom"))
    end_unit()

    assert [record.message for record in spy.handled] == ["boom"]
