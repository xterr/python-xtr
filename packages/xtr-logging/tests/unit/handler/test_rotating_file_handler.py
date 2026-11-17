from __future__ import annotations

import datetime as dt
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING

import pytest
from xtr_clock import MockClock

from tests.support.records import make_record
from xtr_logging import InvalidOptionError
from xtr_logging.formatter.json_batch_mode import JsonBatchMode
from xtr_logging.formatter.json_formatter import JsonFormatter
from xtr_logging.handler.rotating_file_handler import RotatingFileHandler

if TYPE_CHECKING:
    from pathlib import Path

_DAY_ONE = dt.datetime(2026, 9, 24, 8, 0, tzinfo=dt.UTC)
_DAY_TWO = dt.datetime(2026, 9, 25, 8, 0, tzinfo=dt.UTC)
_DAY_THREE = dt.datetime(2026, 9, 26, 8, 0, tzinfo=dt.UTC)


def _handler(
    tmp_path: Path,
    clock: MockClock,
    *,
    max_files: int = 0,
    date_format: str = "%Y-%m-%d",
    filename_format: str = "{filename}-{date}",
) -> RotatingFileHandler:
    return RotatingFileHandler(
        tmp_path / "app.log",
        max_files,
        date_format=date_format,
        filename_format=filename_format,
        clock=clock,
    )


def test_it_writes_to_a_file_named_from_todays_date(tmp_path: Path) -> None:
    handler = _handler(tmp_path, MockClock(_DAY_ONE))

    _ = handler.handle(make_record(message="hello", at=_DAY_ONE))
    handler.close()

    dated = tmp_path / "app-2026-09-24.log"
    assert "hello" in dated.read_text(encoding="utf-8")
    assert not (tmp_path / "app.log").exists()


def test_the_date_comes_from_the_clock_not_the_record(tmp_path: Path) -> None:
    handler = _handler(tmp_path, MockClock(_DAY_ONE))

    _ = handler.handle(make_record(message="old", at=dt.datetime(2020, 1, 2, tzinfo=dt.UTC)))
    handler.close()

    assert [p.name for p in tmp_path.glob("app-*.log")] == ["app-2026-09-24.log"]


def test_a_new_date_switches_to_a_new_file(tmp_path: Path) -> None:
    clock = MockClock(_DAY_ONE)
    handler = _handler(tmp_path, clock)

    _ = handler.handle(make_record(message="one"))
    clock.modify("+1 day")
    _ = handler.handle(make_record(message="two"))
    handler.close()

    assert "one" in (tmp_path / "app-2026-09-24.log").read_text(encoding="utf-8")
    assert "two" in (tmp_path / "app-2026-09-25.log").read_text(encoding="utf-8")


def test_the_same_date_keeps_writing_to_one_file(tmp_path: Path) -> None:
    clock = MockClock(_DAY_ONE)
    handler = _handler(tmp_path, clock)

    _ = handler.handle(make_record(message="a"))
    clock.modify("+12 hours")
    _ = handler.handle(make_record(message="b"))
    handler.close()

    assert [p.name for p in tmp_path.glob("app-*.log")] == ["app-2026-09-24.log"]


def test_the_extension_is_kept_and_the_stem_carries_the_date(tmp_path: Path) -> None:
    handler = RotatingFileHandler(tmp_path / "service.json", clock=MockClock(_DAY_ONE))

    _ = handler.handle(make_record(message="x"))
    handler.close()

    assert (tmp_path / "service-2026-09-24.json").exists()


def test_a_custom_filename_format_places_the_tokens(tmp_path: Path) -> None:
    handler = _handler(tmp_path, MockClock(_DAY_ONE), filename_format="{date}_{filename}")

    _ = handler.handle(make_record(message="x"))
    handler.close()

    assert (tmp_path / "2026-09-24_app.log").exists()


def test_old_files_are_swept_leaving_the_newest(tmp_path: Path) -> None:
    clock = MockClock(_DAY_ONE)
    handler = _handler(tmp_path, clock, max_files=2)

    for _day in range(3):
        _ = handler.handle(make_record(message="x"))
        clock.modify("+1 day")
    handler.close()

    remaining = sorted(p.name for p in tmp_path.glob("app-*.log"))
    assert remaining == ["app-2026-09-25.log", "app-2026-09-26.log"]


def test_unlimited_keeps_every_file(tmp_path: Path) -> None:
    clock = MockClock(_DAY_ONE)
    handler = _handler(tmp_path, clock, max_files=0)

    for _day in range(3):
        _ = handler.handle(make_record(message="x"))
        clock.modify("+1 day")
    handler.close()

    assert len(list(tmp_path.glob("app-*.log"))) == 3


def test_a_filename_format_without_the_date_token_is_refused(tmp_path: Path) -> None:
    with pytest.raises(InvalidOptionError, match="filename_format"):
        _ = RotatingFileHandler(tmp_path / "app.log", filename_format="{filename}")


def test_a_static_date_format_is_refused(tmp_path: Path) -> None:
    with pytest.raises(InvalidOptionError, match="date_format"):
        _ = RotatingFileHandler(tmp_path / "app.log", date_format="static")


def test_a_date_format_with_a_separator_is_refused(tmp_path: Path) -> None:
    with pytest.raises(InvalidOptionError, match="date_format"):
        _ = RotatingFileHandler(tmp_path / "app.log", date_format="%Y/%m/%d")


def test_old_files_are_swept_by_the_date_in_their_name_whatever_its_format(
    tmp_path: Path,
) -> None:
    clock = MockClock(dt.datetime(2026, 1, 31, tzinfo=dt.UTC))
    handler = _handler(tmp_path, clock, max_files=2, date_format="%d-%m-%Y")

    for _day in range(3):
        _ = handler.handle(make_record(message="x"))
        clock.modify("+1 day")
    handler.close()

    remaining = sorted(p.name for p in tmp_path.glob("app-*.log"))
    assert remaining == ["app-01-02-2026.log", "app-02-02-2026.log"]


def test_a_batch_lands_whole_in_todays_file(tmp_path: Path) -> None:
    handler = _handler(tmp_path, MockClock(_DAY_TWO))
    handler.formatter = JsonFormatter(JsonBatchMode.JSON)

    handler.handle_batch(
        [make_record(message="one", at=_DAY_ONE), make_record(message="two", at=_DAY_TWO)]
    )
    handler.close()

    written = (tmp_path / "app-2026-09-25.log").read_text(encoding="utf-8")
    assert written.startswith('[{"message":"one"')
    assert '"message":"two"' in written
    assert [p.name for p in tmp_path.glob("app-*.log")] == ["app-2026-09-25.log"]


def test_threads_writing_across_a_date_change_put_each_record_in_its_dates_file(
    tmp_path: Path,
) -> None:
    clock = MockClock(_DAY_ONE)
    handler = _handler(tmp_path, clock)

    with ThreadPoolExecutor(8) as pool:
        _ = list(pool.map(handler.handle, [make_record(message=f"one-{i}") for i in range(300)]))
    clock.modify("+1 day")
    with ThreadPoolExecutor(8) as pool:
        _ = list(pool.map(handler.handle, [make_record(message=f"two-{i}") for i in range(300)]))
    handler.close()

    first = (tmp_path / "app-2026-09-24.log").read_text(encoding="utf-8").splitlines()
    second = (tmp_path / "app-2026-09-25.log").read_text(encoding="utf-8").splitlines()
    assert len(first) == len(second) == 300
    assert all(": one-" in line for line in first)
    assert all(": two-" in line for line in second)


def test_an_old_record_does_not_switch_files(tmp_path: Path) -> None:
    # A replayed or forged timestamp must not reopen yesterday's file, or sweep today's.
    handler = _handler(tmp_path, MockClock(_DAY_TWO))

    _ = handler.handle(make_record(message="now", at=_DAY_TWO))
    _ = handler.handle(make_record(message="replayed", at=dt.datetime(2020, 1, 2, tzinfo=dt.UTC)))
    handler.close()

    assert [p.name for p in tmp_path.glob("app-*.log")] == ["app-2026-09-25.log"]
    assert "replayed" in (tmp_path / "app-2026-09-25.log").read_text(encoding="utf-8")


def test_the_file_switches_when_the_clock_reaches_the_next_day(tmp_path: Path) -> None:
    clock = MockClock(_DAY_ONE)
    handler = _handler(tmp_path, clock)

    _ = handler.handle(make_record(message="one", at=_DAY_ONE))
    clock.modify("+1 day")
    _ = handler.handle(make_record(message="two", at=_DAY_ONE))
    handler.close()

    assert "one" in (tmp_path / "app-2026-09-24.log").read_text(encoding="utf-8")
    assert "two" in (tmp_path / "app-2026-09-25.log").read_text(encoding="utf-8")
