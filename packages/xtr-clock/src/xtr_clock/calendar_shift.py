"""Moving a date by calendar months and days, the way a person reads a calendar."""

from __future__ import annotations

import calendar
from datetime import UTC, timedelta
from typing import TYPE_CHECKING, Final, TypeVar

if TYPE_CHECKING:
    from datetime import datetime

__all__ = ["shift_calendar"]

_MONTHS_PER_YEAR: Final = 12

_DateT = TypeVar("_DateT", bound="datetime")


def shift_calendar(moment: _DateT, /, *, months: int = 0, days: int = 0) -> _DateT:
    """Move ``moment`` by whole months, then whole days, keeping the wall clock it shows.

    "A month later" from the 31st lands on the last day of a shorter month,
    and "a day later" at 09:00 is at 09:00 again across a clock change — not
    24 hours later. A wall clock the zone skipped over (the hour lost as the
    clocks go forward) is read as the instant it names, shown on the hour
    that replaced it, so the result always really existed.

    Asked for no shift at all — a scheduler stepping a calendar by zero —
    it hands back what it was given, rather than resolving an instant it
    never moved.
    """
    if not months and not days:
        return moment
    if months:
        position = moment.month - 1 + months
        year = moment.year + position // _MONTHS_PER_YEAR
        month = position % _MONTHS_PER_YEAR + 1
        moment = moment.replace(
            year=year, month=month, day=min(moment.day, calendar.monthrange(year, month)[1])
        )
    if days:
        shifted = moment.date() + timedelta(days=days)
        moment = moment.replace(year=shifted.year, month=shifted.month, day=shifted.day)
    if moment.tzinfo is None:
        return moment
    return moment.astimezone(UTC).astimezone(moment.tzinfo)
