"""The little grammar ``'+1 day'`` is written in.

A modifier is read against a reference instant — normally whatever the
current clock says — and answers with another instant. It is the one piece
of this library that parses anything, and it is deliberately small: five
shapes, listed below, and nothing else.

====================  ==================================================
``now``               the reference, unchanged
``+1 day``            an offset; units may be chained and may be negative
``2 days ago``        the same, spelled backwards
``tomorrow``          a keyword: today, tomorrow, yesterday, midnight, noon
``2024-04-09 15:00``  an absolute datetime, in ISO-8601
``Europe/Paris``      the same instant, read in another zone
====================  ==================================================

A term with no sign of its own continues the direction of the one before it,
so ``'-2 hours 30 minutes'`` is two and a half hours back, not one and a
half. Writing a sign again turns around: ``'+1 day -3 hours'`` is a day on
and three hours off.

A zone may trail any of them — ``'+1 day Europe/Paris'`` moves to Paris
first and adds a day there, which is not the same instant as adding a day
and then moving. Anything the grammar does not recognise raises
:class:`~xtr_clock.exception.InvalidModifierError` rather than quietly
resolving to the reference.

Two rules about arithmetic, both chosen to be the least surprising:

* **Calendar units keep the wall clock.** ``'+1 day'`` lands on the same
  time tomorrow even when daylight saving moved the offset in between.
* **Durations keep the elapsed time.** ``'+3 hours'`` is three real hours,
  so across a daylight saving change the wall clock shifts by four.

``'+1 month'`` on the 31st clamps to the last day of the shorter month
rather than spilling into the next one, so adding a month never skips one.
Clamping makes month arithmetic non-associative at month ends — two
separate ``'+1 month'`` steps from January 31 reach March 28, one
``'+2 months'`` step reaches March 31 — which is inherent to calendars, not
a defect here.

Keeping the wall clock can land on one that does not exist, on the day a
zone springs forward. Every result is therefore resolved back through the
instant it names, so what comes out is a wall clock that was really on the
wall — an hour later than asked for, which is the hour that went missing.
"""

from __future__ import annotations

import calendar
import re
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Final

from .exception import InvalidModifierError, InvalidTimezoneError
from .timezone import resolve_timezone

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

__all__ = ["apply_modifier"]

_MONTHS_PER_YEAR: Final = 12
_DAYS_PER_WEEK: Final = 7
_LAST_MONTH: Final = 12

# One term of an offset: an optional sign, a count, a unit, an optional comma.
_TERM: Final = re.compile(r"\s*(?P<sign>[+-]?)\s*(?P<amount>\d+)\s*(?P<unit>[a-zA-Z]+)\s*,?")

# ISO-8601 stops short of a bare year and month, and '2024-04' is a useful
# thing to write, so it is recognised here as the first of that month.
_YEAR_MONTH: Final = re.compile(r"^(?P<year>\d{4})-(?P<month>\d{2})$")

_AGO: Final = "ago"

# Spellings that mean the same unit. Single letters are left out on purpose:
# 'm' reads as both minute and month, and a modifier should never be a guess.
_UNITS: Final[Mapping[str, str]] = {
    "year": "years",
    "years": "years",
    "yr": "years",
    "yrs": "years",
    "month": "months",
    "months": "months",
    "week": "weeks",
    "weeks": "weeks",
    "day": "days",
    "days": "days",
    "hour": "hours",
    "hours": "hours",
    "hr": "hours",
    "hrs": "hours",
    "minute": "minutes",
    "minutes": "minutes",
    "min": "minutes",
    "mins": "minutes",
    "second": "seconds",
    "seconds": "seconds",
    "sec": "seconds",
    "secs": "seconds",
    "millisecond": "milliseconds",
    "milliseconds": "milliseconds",
    "msec": "milliseconds",
    "msecs": "milliseconds",
    "microsecond": "microseconds",
    "microseconds": "microseconds",
    "usec": "microseconds",
    "usecs": "microseconds",
}

# Units that measure elapsed time rather than calendar position.
_DURATIONS: Final[Mapping[str, timedelta]] = {
    "hours": timedelta(hours=1),
    "minutes": timedelta(minutes=1),
    "seconds": timedelta(seconds=1),
    "milliseconds": timedelta(milliseconds=1),
    "microseconds": timedelta(microseconds=1),
}


def apply_modifier(reference: datetime, modifier: str) -> datetime:
    """Return the instant ``modifier`` describes, read against ``reference``.

    Args:
        reference: The instant the modifier is relative to.
        modifier: One of the shapes documented on this module.

    Returns:
        The instant described, in the zone the modifier named or, when it
        named none, in the zone ``reference`` already carried.

    Raises:
        InvalidModifierError: When the grammar cannot read ``modifier``.
    """
    spec = modifier.strip()
    if not spec:
        raise InvalidModifierError(modifier, "it is empty")

    moment, rest = _split_timezone(reference, spec)
    if not rest or rest.lower() == "now":
        return moment

    if (keyword := _KEYWORDS.get(rest.lower())) is not None:
        return _normalise(keyword(moment))

    if (offset := _read_offset(rest)) is not None:
        return _normalise(_shift(moment, *offset))

    if (absolute := _read_absolute(rest, moment)) is not None:
        return _normalise(absolute)

    raise InvalidModifierError(
        modifier,
        "it is neither an offset like '+1 day', a keyword like 'tomorrow', "
        "an ISO-8601 datetime, nor a timezone name",
    )


def _split_timezone(reference: datetime, spec: str) -> tuple[datetime, str]:
    """Split a trailing timezone off ``spec``, moving ``reference`` into it.

    The zone is applied before anything else, so an offset in the rest of
    the modifier is counted in the zone the caller asked for.
    """
    tokens = spec.split()
    try:
        zone = resolve_timezone(tokens[-1])
    except InvalidTimezoneError:
        return reference, spec

    return reference.astimezone(zone), " ".join(tokens[:-1])


def _read_offset(text: str) -> tuple[int, int, timedelta] | None:
    """Read ``text`` as an offset, or return ``None`` when it is not one.

    Returns:
        The months, the days and the duration the offset adds up to, kept
        apart because each is applied differently.
    """
    tokens = text.split()
    backwards = bool(tokens) and tokens[-1].lower() == _AGO
    body = " ".join(tokens[:-1]) if backwards else " ".join(tokens)
    if not body:
        return None

    months = 0
    days = 0
    duration = timedelta()
    position = 0
    sign = 1

    while position < len(body):
        term = _TERM.match(body, position)
        if term is None:
            return None

        unit = _UNITS.get(term["unit"].lower())
        if unit is None:
            return None

        # A term without a sign of its own continues the one before it, so
        # '-2 hours 30 minutes' is two and a half hours back rather than one
        # and a half. Writing a sign again is what changes direction.
        if term["sign"]:
            sign = -1 if term["sign"] == "-" else 1

        amount = sign * int(term["amount"])
        if unit == "years":
            months += amount * _MONTHS_PER_YEAR
        elif unit == "months":
            months += amount
        elif unit == "weeks":
            days += amount * _DAYS_PER_WEEK
        elif unit == "days":
            days += amount
        else:
            duration += _DURATIONS[unit] * amount

        position = term.end()

    return (-months, -days, -duration) if backwards else (months, days, duration)


def _read_absolute(text: str, moment: datetime) -> datetime | None:
    """Read ``text`` as an absolute datetime, or return ``None``.

    A reading that names no zone of its own is taken in the zone ``moment``
    carries, and one that names only a date starts at midnight.
    """
    if (bounds := _YEAR_MONTH.match(text)) and 1 <= int(bounds["month"]) <= _LAST_MONTH:
        return _midnight(
            moment.replace(year=int(bounds["year"]), month=int(bounds["month"]), day=1),
        )

    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None

    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=moment.tzinfo)


def _shift(moment: datetime, months: int, days: int, duration: timedelta) -> datetime:
    """Move ``moment`` by a calendar offset and then by an elapsed one."""
    zone = moment.tzinfo

    if months:
        moment = _shift_months(moment, months)
    if days:
        moment = _shift_days(moment, days)
    if duration:
        moment = (
            moment + duration
            if zone is None
            else (moment.astimezone(UTC) + duration).astimezone(zone)
        )

    return moment


def _shift_months(moment: datetime, months: int) -> datetime:
    """Move ``moment`` by whole months, clamping to the end of a shorter one."""
    position = moment.month - 1 + months
    year = moment.year + position // _MONTHS_PER_YEAR
    month = position % _MONTHS_PER_YEAR + 1

    return moment.replace(
        year=year,
        month=month,
        day=min(moment.day, calendar.monthrange(year, month)[1]),
    )


def _shift_days(moment: datetime, days: int) -> datetime:
    """Move ``moment`` by whole days, keeping the wall clock it shows."""
    shifted = moment.date() + timedelta(days=days)

    return moment.replace(year=shifted.year, month=shifted.month, day=shifted.day)


def _normalise(moment: datetime) -> datetime:
    """Return the same instant, shown on a wall clock that really existed.

    Keeping the wall clock through a calendar shift can name a time a zone
    skipped over. Resolving the instant and reading it back moves the label
    onto the hour that replaced it, and leaves every other reading alone.
    """
    if moment.tzinfo is None:
        return moment

    return moment.astimezone(UTC).astimezone(moment.tzinfo)


def _midnight(moment: datetime) -> datetime:
    """Return the start of the day ``moment`` falls in."""
    return moment.replace(hour=0, minute=0, second=0, microsecond=0)


def _noon(moment: datetime) -> datetime:
    """Return midday on the day ``moment`` falls in."""
    return moment.replace(hour=12, minute=0, second=0, microsecond=0)


_KEYWORDS: Final[Mapping[str, Callable[[datetime], datetime]]] = {
    "today": _midnight,
    "midnight": _midnight,
    "noon": _noon,
    "tomorrow": lambda moment: _midnight(_shift_days(moment, 1)),
    "yesterday": lambda moment: _midnight(_shift_days(moment, -1)),
}
