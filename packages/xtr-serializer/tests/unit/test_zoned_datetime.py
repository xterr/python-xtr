"""A datetime written with its zone's name, read back in that zone, the repeated hour included."""

from __future__ import annotations

import zoneinfo
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import cast
from zoneinfo import ZoneInfo

import pytest
from pydantic import TypeAdapter, ValidationError
from pydantic_core import PydanticSerializationError
from xtr_clock import DatePoint

from tests.fixtures.nameless import NamelessThing, names_refused
from xtr_serializer import ZonedDateTime
from xtr_serializer.exception import NotNormalizableValueError

BUCHAREST = ZoneInfo("Europe/Bucharest")
ZONED: TypeAdapter[datetime] = TypeAdapter(ZonedDateTime)

# 2026-10-25: Bucharest sets its clocks back from 04:00 to 03:00, so 03:30 happens twice.
FIRST_HALF_PAST_THREE = datetime(2026, 10, 25, 3, 30, tzinfo=BUCHAREST)
SECOND_HALF_PAST_THREE = datetime(2026, 10, 25, 3, 30, fold=1, tzinfo=BUCHAREST)


def read_back(value: datetime) -> datetime:
    return ZONED.validate_json(ZONED.dump_json(value))


@pytest.mark.parametrize(
    ("value", "written"),
    [
        (FIRST_HALF_PAST_THREE, '"2026-10-25T03:30:00+03:00[Europe/Bucharest]"'),
        (SECOND_HALF_PAST_THREE, '"2026-10-25T03:30:00+02:00[Europe/Bucharest]"'),
    ],
    ids=["first", "repeated"],
)
def test_it_writes_the_datetime_with_its_offset_then_the_zone_name(
    value: datetime, written: str
) -> None:
    assert ZONED.dump_json(value).decode() == written


@pytest.mark.parametrize(
    "value",
    [
        FIRST_HALF_PAST_THREE,
        SECOND_HALF_PAST_THREE,
        datetime(2026, 7, 1, 12, 0, 0, 123456, tzinfo=ZoneInfo("America/New_York")),
        datetime(1890, 1, 1, tzinfo=BUCHAREST),  # local mean time, an offset in seconds
    ],
    ids=["first", "repeated", "summer", "seconds-offset"],
)
def test_it_reads_back_equal_in_the_same_zone_and_fold(value: datetime) -> None:
    read = read_back(value)

    assert read == value
    assert type(read) is datetime
    assert read.tzinfo is value.tzinfo
    assert read.fold == value.fold


def test_it_tells_the_two_repeated_hours_apart() -> None:
    first, second = read_back(FIRST_HALF_PAST_THREE), read_back(SECOND_HALF_PAST_THREE)

    assert second.astimezone(UTC) - first.astimezone(UTC) == timedelta(hours=1)


def test_a_date_point_reads_back_as_a_datetime_in_its_zone() -> None:
    point = DatePoint(2026, 10, 25, 3, 30, tzinfo=BUCHAREST, fold=1)

    read = read_back(point)

    assert (read, read.fold, read.tzinfo) == (point, 1, BUCHAREST)
    assert type(read) is datetime


def test_python_input_already_in_a_zone_is_taken_as_it_is() -> None:
    assert ZONED.validate_python(SECOND_HALF_PAST_THREE) is SECOND_HALF_PAST_THREE


def test_it_keeps_a_python_dump_a_datetime() -> None:
    assert ZONED.dump_python(SECOND_HALF_PAST_THREE) is SECOND_HALF_PAST_THREE


@pytest.mark.parametrize(
    ("value", "words"),
    [
        (datetime(2026, 1, 1), "is naive"),  # noqa: DTZ001 - a naive datetime is the point
        (datetime(2026, 1, 1, tzinfo=timezone(timedelta(hours=2))), "fixed offset"),
        (datetime(2026, 1, 1, tzinfo=UTC), "fixed offset"),
        ("2026-01-01T00:00:00+00:00[UTC]", "not a datetime"),
    ],
    ids=["naive", "offset", "utc-constant", "not-a-datetime"],
)
def test_it_refuses_to_write_a_datetime_without_a_named_zone(value: object, words: str) -> None:
    with pytest.raises(PydanticSerializationError) as raised:
        _ = cast("object", cast("TypeAdapter[object]", ZONED).dump_python(value, mode="json"))

    refusal = raised.value.__cause__
    assert isinstance(refusal, NotNormalizableValueError)
    assert words in refusal.message
    assert refusal.error_type == "zoned_datetime"


def test_it_names_what_is_not_a_datetime_without_running_its_metaclass() -> None:
    zoned = cast("TypeAdapter[object]", ZONED)

    with names_refused(), pytest.raises(PydanticSerializationError) as raised:
        _ = cast("object", zoned.dump_python(NamelessThing(), mode="json"))

    refusal = raised.value.__cause__
    assert isinstance(refusal, NotNormalizableValueError)
    assert refusal.current_type == "NamelessThing"


def test_it_refuses_to_write_a_zone_read_from_a_file_which_has_no_name() -> None:
    found = [Path(root, "Europe", "Bucharest") for root in zoneinfo.TZPATH]
    files = [path for path in found if path.is_file()]
    if not files:
        pytest.skip("the system keeps no zone files")
    with files[0].open("rb") as file:
        unnamed = ZoneInfo.from_file(file)

    with pytest.raises(PydanticSerializationError) as raised:
        _ = cast("object", ZONED.dump_python(datetime(2026, 1, 1, tzinfo=unnamed), mode="json"))

    assert isinstance(raised.value.__cause__, NotNormalizableValueError)
    assert "no name" in raised.value.__cause__.message


PLANTED = "s3cr3t-t0ken-4f9a"


@pytest.mark.parametrize(
    "written",
    [
        f'"{PLANTED}"',
        f'"2026-01-01T00:00:00+02:00[Europe/{PLANTED}]"',
        f'"2026-01-01T00:00:00+02:00[../../{PLANTED}]"',
        '"2026-01-01T00:00:00+02:00[Europe]"',
        f'"2026-13-01T00:{PLANTED}[Europe/Bucharest]"',
        '"2026-01-01T00:00:00[Europe/Bucharest]"',
        '"2026-10-25T03:30:00+05:00[Europe/Bucharest]"',
        "1",
        f'"2026-01-01T00:00:00+02:00[Europe/Bucharest][{PLANTED}]"',
    ],
    ids=[
        "no-zone",
        "unknown-zone",
        "path-as-zone",
        "directory-as-zone",
        "bad-datetime",
        "naive",
        "offset-the-zone-does-not-give",
        "not-a-string",
        "two-zones",
    ],
)
def test_it_refuses_to_read_what_is_not_a_zoned_datetime_without_quoting_it(written: str) -> None:
    with pytest.raises(ValidationError) as raised:
        _ = ZONED.validate_json(written)

    [error] = raised.value.errors(include_input=False)
    assert error["type"] == "zoned_datetime"
    assert PLANTED not in error["msg"]


def test_it_refuses_python_input_with_a_fixed_offset() -> None:
    with pytest.raises(ValidationError) as raised:
        _ = ZONED.validate_python(datetime(2026, 1, 1, tzinfo=UTC))

    assert raised.value.errors()[0]["type"] == "zoned_datetime"


@pytest.mark.parametrize(
    "written",
    [
        '"9999-12-31T23:00:00-05:00[America/New_York]"',
        '"0001-01-01T00:30:00+09:18:59[Asia/Tokyo]"',
    ],
    ids=["last-year", "first-year"],
)
def test_it_refuses_a_time_whose_instant_falls_outside_the_years_a_datetime_holds(
    written: str,
) -> None:
    with pytest.raises(ValidationError) as raised:
        _ = ZONED.validate_json(written)

    assert raised.value.errors()[0]["type"] == "zoned_datetime"
