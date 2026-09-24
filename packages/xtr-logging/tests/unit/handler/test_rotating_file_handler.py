from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING

import pytest

from tests.support.records import make_record
from xtr_logging import InvalidOptionError
from xtr_logging.handler.rotating_file_handler import RotatingFileHandler

if TYPE_CHECKING:
    from pathlib import Path

_DAY_ONE = dt.datetime(2026, 9, 24, 8, 0, tzinfo=dt.UTC)
_DAY_TWO = dt.datetime(2026, 9, 25, 8, 0, tzinfo=dt.UTC)
_DAY_THREE = dt.datetime(2026, 9, 26, 8, 0, tzinfo=dt.UTC)


def test_it_writes_to_a_file_named_from_the_records_date(tmp_path: Path) -> None:
    handler = RotatingFileHandler(tmp_path / "app.log")

    _ = handler.handle(make_record(message="hello", at=_DAY_ONE))
    handler.close()

    dated = tmp_path / "app-2026-09-24.log"
    assert "hello" in dated.read_text(encoding="utf-8")
    assert not (tmp_path / "app.log").exists()


def test_the_date_comes_from_the_record_not_the_wall_clock(tmp_path: Path) -> None:
    handler = RotatingFileHandler(tmp_path / "app.log")

    _ = handler.handle(make_record(message="old", at=dt.datetime(2020, 1, 2, tzinfo=dt.UTC)))
    handler.close()

    assert (tmp_path / "app-2020-01-02.log").exists()


def test_a_new_date_switches_to_a_new_file(tmp_path: Path) -> None:
    handler = RotatingFileHandler(tmp_path / "app.log")

    _ = handler.handle(make_record(message="one", at=_DAY_ONE))
    _ = handler.handle(make_record(message="two", at=_DAY_TWO))
    handler.close()

    assert "one" in (tmp_path / "app-2026-09-24.log").read_text(encoding="utf-8")
    assert "two" in (tmp_path / "app-2026-09-25.log").read_text(encoding="utf-8")


def test_the_same_date_keeps_writing_to_one_file(tmp_path: Path) -> None:
    handler = RotatingFileHandler(tmp_path / "app.log")

    _ = handler.handle(make_record(message="a", at=_DAY_ONE))
    _ = handler.handle(make_record(message="b", at=_DAY_ONE.replace(hour=20)))
    handler.close()

    assert [p.name for p in tmp_path.glob("app-*.log")] == ["app-2026-09-24.log"]


def test_the_extension_is_kept_and_the_stem_carries_the_date(tmp_path: Path) -> None:
    handler = RotatingFileHandler(tmp_path / "service.json")

    _ = handler.handle(make_record(message="x", at=_DAY_ONE))
    handler.close()

    assert (tmp_path / "service-2026-09-24.json").exists()


def test_a_custom_filename_format_places_the_tokens(tmp_path: Path) -> None:
    handler = RotatingFileHandler(tmp_path / "app.log", filename_format="{date}_{filename}")

    _ = handler.handle(make_record(message="x", at=_DAY_ONE))
    handler.close()

    assert (tmp_path / "2026-09-24_app.log").exists()


def test_old_files_are_swept_leaving_the_newest(tmp_path: Path) -> None:
    handler = RotatingFileHandler(tmp_path / "app.log", max_files=2)

    for day in (_DAY_ONE, _DAY_TWO, _DAY_THREE):
        _ = handler.handle(make_record(message="x", at=day))
    handler.close()

    remaining = sorted(p.name for p in tmp_path.glob("app-*.log"))
    assert remaining == ["app-2026-09-25.log", "app-2026-09-26.log"]


def test_unlimited_keeps_every_file(tmp_path: Path) -> None:
    handler = RotatingFileHandler(tmp_path / "app.log", max_files=0)

    for day in (_DAY_ONE, _DAY_TWO, _DAY_THREE):
        _ = handler.handle(make_record(message="x", at=day))
    handler.close()

    assert len(list(tmp_path.glob("app-*.log"))) == 3


def test_a_filename_format_without_the_date_token_is_refused(tmp_path: Path) -> None:
    with pytest.raises(InvalidOptionError, match="filename_format"):
        _ = RotatingFileHandler(tmp_path / "app.log", filename_format="{filename}")


def test_a_static_date_format_is_refused(tmp_path: Path) -> None:
    with pytest.raises(InvalidOptionError, match="date_format"):
        _ = RotatingFileHandler(tmp_path / "app.log", date_format="static")
