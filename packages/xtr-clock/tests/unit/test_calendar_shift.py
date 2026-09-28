from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from xtr_clock import DatePoint, shift_calendar

BUCHAREST = ZoneInfo("Europe/Bucharest")


def test_a_month_from_the_31st_lands_on_the_last_day_of_a_shorter_month() -> None:
    assert shift_calendar(datetime(2026, 1, 31, 9, tzinfo=BUCHAREST), months=1) == datetime(
        2026, 2, 28, 9, tzinfo=BUCHAREST
    )


def test_a_day_keeps_the_wall_clock_across_a_clock_change() -> None:
    shifted = shift_calendar(datetime(2026, 3, 28, 9, tzinfo=BUCHAREST), days=1)

    assert (shifted.day, shifted.hour, shifted.utcoffset()) == (29, 9, BUCHAREST.utcoffset(shifted))


def test_a_wall_clock_the_zone_skipped_is_shown_on_the_hour_that_replaced_it() -> None:
    shifted = shift_calendar(datetime(2026, 3, 27, 3, 30, tzinfo=BUCHAREST), days=2)

    assert shifted.isoformat() == "2026-03-29T04:30:00+03:00"


def test_a_date_point_stays_a_date_point() -> None:
    moment = DatePoint(2026, 1, 1, tzinfo=BUCHAREST)

    assert isinstance(shift_calendar(moment, months=1), DatePoint)
