"""An instant stored in UTC, and read back knowing it is in UTC."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import DateTime
from sqlalchemy.dialects import sqlite
from xtr_clock import DatePoint
from xtr_security_oauth2_server_core.exception.invalid_argument_error import InvalidArgumentError

from tests.support.orm import round_trip
from xtr_security_oauth2_server.persistence.type.utc_datetime import UtcDateTime

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.anyio

_DIALECT = sqlite.dialect()
_AT_NOON = datetime(2026, 3, 4, 12, 0, 0, tzinfo=UTC)
_BUCHAREST = ZoneInfo("Europe/Bucharest")


@pytest.fixture
def east_of_utc(monkeypatch: pytest.MonkeyPatch) -> None:
    """Run on a machine east of UTC, where a value labelled with the local zone is hours off."""
    monkeypatch.setenv("TZ", "Europe/Bucharest")


def _assert_stored_as(value: datetime | None, instant: datetime, wall_clock: datetime) -> None:
    """Assert ``value`` is what a driver must be handed: exactly a plain naive UTC ``datetime``.

    Exactly ``datetime``: one driver picks its encoder by the exact type and sends a subclass as
    text, offset and all; the others read the zone, refusing it or converting it. The instant is
    compared by timestamp, which a repeated hour cannot mislead.
    """
    assert type(value) is datetime
    assert value.tzinfo is None
    assert value == wall_clock
    assert value.replace(tzinfo=UTC).timestamp() == instant.timestamp()


def test_it_stores_a_plain_timestamp_so_every_database_reads_the_same() -> None:
    stored = UtcDateTime().impl_instance

    assert isinstance(stored, DateTime)
    assert stored.timezone is False


def test_an_instant_goes_in_without_its_zone_because_it_is_already_utc() -> None:
    assert UtcDateTime().process_bind_param(_AT_NOON, _DIALECT) == datetime(2026, 3, 4, 12, 0, 0)  # noqa: DTZ001 -- the stored value is deliberately naive


def test_an_instant_in_another_zone_is_moved_to_utc_before_it_is_stored() -> None:
    elsewhere = datetime(2026, 3, 4, 14, 0, 0, tzinfo=timezone(timedelta(hours=2)))

    assert UtcDateTime().process_bind_param(elsewhere, _DIALECT) == datetime(2026, 3, 4, 12, 0, 0)  # noqa: DTZ001 -- the stored value is deliberately naive


def test_nothing_goes_in_as_nothing() -> None:
    assert UtcDateTime().process_bind_param(None, _DIALECT) is None


def test_a_stored_timestamp_comes_back_knowing_it_is_utc() -> None:
    read = UtcDateTime().process_result_value(datetime(2026, 3, 4, 12, 0, 0), _DIALECT)  # noqa: DTZ001 -- what a database without zones hands back

    assert read == _AT_NOON
    assert read is not None
    assert read.tzinfo is UTC


def test_nothing_stored_comes_back_as_nothing() -> None:
    assert UtcDateTime().process_result_value(None, _DIALECT) is None


def test_a_naive_instant_is_refused_rather_than_guessed_at() -> None:
    with pytest.raises(InvalidArgumentError, match="time zone"):
        _ = UtcDateTime().process_bind_param(datetime(2026, 3, 4, 12, 0, 0), _DIALECT)  # noqa: DTZ001 -- the point of the test is an instant with no zone


async def test_an_instant_survives_a_trip_through_a_database(tmp_path: Path) -> None:
    assert await round_trip(tmp_path, UtcDateTime(), _AT_NOON) == _AT_NOON


async def test_nothing_survives_a_trip_through_a_database_as_nothing(tmp_path: Path) -> None:
    assert await round_trip(tmp_path, UtcDateTime(), None) is None


def test_it_may_be_cached_so_a_query_on_it_is_not_recompiled_every_time() -> None:
    assert isinstance(UtcDateTime()._static_cache_key, tuple)


@pytest.mark.usefixtures("east_of_utc")
def test_a_clock_reading_goes_in_as_a_plain_naive_utc_datetime() -> None:
    reading = DatePoint(2026, 11, 10, 10, 8, 54, 84887, tzinfo=UTC)

    stored = UtcDateTime().process_bind_param(reading, _DIALECT)

    _assert_stored_as(stored, reading, datetime(2026, 11, 10, 10, 8, 54, 84887))  # noqa: DTZ001 -- the stored value is deliberately naive


@pytest.mark.usefixtures("east_of_utc")
@pytest.mark.parametrize(
    ("reading", "wall_clock"),
    [
        (
            DatePoint(2026, 11, 10, 15, 38, 54, tzinfo=timezone(timedelta(hours=5, minutes=30))),
            (10, 8),
        ),
        (DatePoint(2026, 11, 10, 5, 8, 54, tzinfo=timezone(timedelta(hours=-5))), (10, 8)),
        (DatePoint(2026, 11, 10, 12, 8, 54, tzinfo=_BUCHAREST), (10, 8)),
        (DatePoint(2026, 7, 10, 13, 8, 54, tzinfo=_BUCHAREST), (10, 8)),
    ],
    ids=["east", "west", "winter", "summer"],
)
def test_a_clock_reading_in_another_zone_goes_in_as_its_utc_instant(
    reading: DatePoint,
    wall_clock: tuple[int, int],
) -> None:
    stored = UtcDateTime().process_bind_param(reading, _DIALECT)

    expected = datetime(reading.year, reading.month, reading.day, *wall_clock, 54)  # noqa: DTZ001 -- the stored value is deliberately naive
    _assert_stored_as(stored, reading, expected)


@pytest.mark.usefixtures("east_of_utc")
def test_a_clock_reading_in_the_local_zone_goes_in_as_its_utc_instant() -> None:
    reading = DatePoint(2026, 11, 10, 12, 8, 54)

    stored = UtcDateTime().process_bind_param(reading, _DIALECT)

    _assert_stored_as(stored, reading, datetime(2026, 11, 10, 10, 8, 54))  # noqa: DTZ001 -- the stored value is deliberately naive


@pytest.mark.parametrize(("fold", "utc_hour"), [(0, 0), (1, 1)])
def test_a_reading_in_a_repeated_hour_goes_in_as_the_instant_it_names(
    fold: int,
    utc_hour: int,
) -> None:
    reading = DatePoint(2026, 10, 25, 3, 30, tzinfo=_BUCHAREST, fold=fold)

    stored = UtcDateTime().process_bind_param(reading, _DIALECT)

    _assert_stored_as(stored, reading, datetime(2026, 10, 25, utc_hour, 30))  # noqa: DTZ001 -- the stored value is deliberately naive


def test_a_plain_datetime_in_a_repeated_hour_keeps_its_fold() -> None:
    later = datetime(2026, 10, 25, 3, 30, tzinfo=_BUCHAREST, fold=1)

    stored = UtcDateTime().process_bind_param(later, _DIALECT)

    _assert_stored_as(stored, later, datetime(2026, 10, 25, 1, 30))  # noqa: DTZ001 -- the stored value is deliberately naive


def test_a_naive_clock_reading_is_refused_like_any_naive_instant() -> None:
    # Around the constructor, which would attach the local zone: a naive DatePoint on every
    # Python version.
    naive = datetime.__new__(DatePoint, 2026, 11, 10, 10, 8, 54)

    with pytest.raises(InvalidArgumentError, match="time zone"):
        _ = UtcDateTime().process_bind_param(naive, _DIALECT)


@pytest.mark.usefixtures("east_of_utc")
async def test_a_clock_reading_survives_a_trip_through_a_database(tmp_path: Path) -> None:
    reading = DatePoint(2026, 11, 10, 12, 8, 54, 84887, tzinfo=_BUCHAREST)

    read = await round_trip(tmp_path, UtcDateTime(), reading)

    assert type(read) is datetime
    assert read.tzinfo is UTC
    assert read.timestamp() == reading.timestamp()


def test_what_comes_back_is_a_plain_datetime_in_utc() -> None:
    read = UtcDateTime().process_result_value(datetime(2026, 11, 10, 10, 8, 54, 84887), _DIALECT)  # noqa: DTZ001 -- what a database without zones hands back

    assert type(read) is datetime
    assert read.tzinfo is UTC
    assert read == datetime(2026, 11, 10, 10, 8, 54, 84887, tzinfo=UTC)
