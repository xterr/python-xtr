from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from xtr_mime.exception import InvalidArgumentError
from xtr_mime.header import DateHeader

BERLIN_NEW_YEAR = datetime(2000, 1, 1, 12, tzinfo=ZoneInfo("Europe/Berlin"))


def test_get_date_time() -> None:
    now = datetime.now(UTC)

    assert DateHeader("Date", now).get_date_time() == now


def test_the_date_time_can_be_set_by_the_setter() -> None:
    header = DateHeader("Date", datetime.now(UTC))
    later = datetime.now(UTC) + timedelta(hours=1)

    header.set_date_time(later)

    assert header.get_date_time() == later


def test_the_date_time_keeps_its_own_offset() -> None:
    offset = timezone(timedelta(hours=-5, minutes=-30))
    date = datetime(2000, 1, 1, 12, tzinfo=offset)

    header = DateHeader("Date", date)

    # Adapted: a datetime is already immutable; what is checked is that the offset stays.
    assert header.get_date_time().utcoffset() == timedelta(hours=-5, minutes=-30)
    assert header.get_body_as_string() == "Sat, 01 Jan 2000 12:00:00 -0530"


def test_the_date_time_is_independent_of_a_copy_changed_later() -> None:
    header = DateHeader("Date", BERLIN_NEW_YEAR)

    # Adapted: "changing" a datetime makes a new one, which leaves the header's as it was.
    _ = BERLIN_NEW_YEAR.replace(year=2002, month=2, day=2)

    assert header.get_body_as_string() == "Sat, 01 Jan 2000 12:00:00 +0100"


def test_the_date_time_is_written_as_an_rfc_2822_date() -> None:
    header = DateHeader("Date", datetime.now(UTC))

    header.set_date_time(BERLIN_NEW_YEAR)

    assert header.get_body_as_string() == "Sat, 01 Jan 2000 12:00:00 +0100"


def test_set_body() -> None:
    header = DateHeader("Date", datetime.now(UTC))

    header.set_body(BERLIN_NEW_YEAR)

    assert header.get_body_as_string() == "Sat, 01 Jan 2000 12:00:00 +0100"


def test_set_body_refuses_what_is_not_a_datetime() -> None:
    header = DateHeader("Date", BERLIN_NEW_YEAR)

    with pytest.raises(InvalidArgumentError):
        header.set_body("Sat, 01 Jan 2000 12:00:00 +0100")


def test_get_body() -> None:
    header = DateHeader("Date", datetime.now(UTC))

    header.set_date_time(BERLIN_NEW_YEAR)

    assert header.get_body() == BERLIN_NEW_YEAR


def test_to_string() -> None:
    assert (
        DateHeader("Date", BERLIN_NEW_YEAR).to_string() == "Date: Sat, 01 Jan 2000 12:00:00 +0100"
    )
