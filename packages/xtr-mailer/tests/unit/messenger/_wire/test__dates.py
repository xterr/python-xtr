"""A date as a queued email carries it: its zone and, in an hour the clocks repeat, which one."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from xtr_mailer.exception import InvalidArgumentError
from xtr_mailer.messenger._wire._dates import read_date, write_date

_BUCHAREST = ZoneInfo("Europe/Bucharest")


def _back(date: datetime) -> datetime:
    return read_date(write_date(date), "date")


def test_a_date_in_a_zone_is_written_with_its_offset_and_the_zone_name() -> None:
    date = datetime(2026, 10, 25, 3, 30, tzinfo=_BUCHAREST, fold=1)

    assert write_date(date) == "2026-10-25T03:30:00+02:00[Europe/Bucharest]"


@pytest.mark.parametrize("fold", [0, 1])
def test_a_date_in_an_hour_the_clocks_repeat_comes_back_the_same_one(fold: int) -> None:
    date = datetime(2026, 10, 25, 3, 30, tzinfo=_BUCHAREST, fold=fold)

    back = _back(date)

    assert (back.tzinfo, back.fold, back.utcoffset()) == (_BUCHAREST, fold, date.utcoffset())


def test_a_date_in_utc_comes_back_in_utc() -> None:
    date = datetime(2026, 11, 3, 9, 30, 15, 120, tzinfo=UTC)

    back = _back(date)

    assert (back, back.tzinfo) == (date, UTC)


def test_a_date_at_a_fixed_offset_comes_back_at_that_offset() -> None:
    offset = timezone(timedelta(hours=2))

    back = _back(datetime(2026, 11, 3, 9, 30, tzinfo=offset))

    assert (back, back.tzinfo) == (datetime(2026, 11, 3, 9, 30, tzinfo=offset), offset)


def test_a_date_without_an_offset_comes_back_without_one() -> None:
    date = datetime(2026, 11, 3, 9, 30)  # noqa: DTZ001 -- one of unknown offset, on purpose.

    back = _back(date)

    assert (back, back.tzinfo) == (date, None)


@pytest.mark.parametrize(
    "data",
    [
        "2026-10-25T03:30:00+02:00[Europe/Nowhere]",
        "2026-10-25T03:30:00+02:00[../../etc/passwd]",
        "2026-10-25T03:30:00+02:00[/etc/localtime]",
        "2026-10-25T03:30:00+05:00[Europe/Bucharest]",
        "2026-10-25T03:30:00[Europe/Bucharest]",
        "2026-10-25T03:30:00+02:00[]",
        "2026-13-01T00:00:00+02:00",
        "not a date",
        "2026-10-25T03:30:00+02:00[Europe/" + "A" * 200 + "]",
        3,
    ],
    ids=[
        "unknown zone",
        "path",
        "absolute path",
        "offset the zone has not",
        "no offset",
        "empty zone",
        "no such month",
        "no date",
        "long",
        "number",
    ],
)
def test_a_date_that_is_not_one_written_here_is_refused(data: object) -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = read_date(data, "date")

    assert str(raised.value).startswith("The queued email cannot be read: date is ")
    assert "Nowhere" not in str(raised.value)
    assert "passwd" not in str(raised.value)
