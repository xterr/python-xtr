"""Turning a timezone name into something a datetime can carry.

Every entry point in this library accepts a timezone as a string as well as
a :class:`~datetime.tzinfo`, because a zone almost always arrives as
configuration — an environment variable, a column, a request header. This is
the one place that conversion happens, so a name this system does not know
fails the same way everywhere.
"""

from __future__ import annotations

import os
import re
from datetime import UTC, datetime, timedelta, tzinfo
from datetime import timezone as fixed_offset
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .exception import InvalidTimezoneError

__all__ = ["local_timezone", "resolve_timezone"]

# '+02:00', '-0530', 'Z'. Anything else is looked up as an IANA name.
_OFFSET = re.compile(r"^(?P<sign>[+-])(?P<hours>\d{2}):?(?P<minutes>\d{2})$")

_MAX_OFFSET_HOURS = 24
_MINUTES_PER_HOUR = 60


def resolve_timezone(timezone: str | tzinfo) -> tzinfo:
    """Return ``timezone`` as a :class:`~datetime.tzinfo`.

    A :class:`~datetime.tzinfo` is returned unchanged, so passing one already
    resolved costs nothing. A string is read as ``'Z'``, a fixed offset like
    ``'+02:00'`` or ``'-0530'``, or an IANA name like ``'Europe/Paris'``.

    Prefer an IANA name: a fixed offset cannot know when daylight saving
    starts, so a date six months away lands on the wrong wall clock.

    Args:
        timezone: A name, an offset, or an already-resolved timezone.

    Returns:
        The resolved timezone.

    Raises:
        InvalidTimezoneError: When the name is not one this system knows.
    """
    if isinstance(timezone, tzinfo):
        return timezone

    # Not an IANA lookup: UTC is the one zone needing no database behind it,
    # so a machine carrying no zone data can still read a clock — and every
    # default here lands on this branch, making them all the same object.
    if timezone in {"Z", "z", "UTC", "utc"}:
        return UTC

    if match := _OFFSET.match(timezone):
        return _fixed_offset(timezone, match)

    try:
        return ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError) as error:
        raise InvalidTimezoneError(timezone) from error


def local_timezone() -> tzinfo:
    """Return the timezone this machine is configured for.

    ``TZ`` wins when it names a zone this system knows, which is how a
    container is usually told where it lives. Otherwise the offset the
    operating system reports for the current instant is used — that is a
    fixed offset, so it carries the right wall clock now but knows nothing
    about the next daylight saving change.

    A program that computes dates months out should name its zone rather
    than inherit this one.
    """
    if configured := os.environ.get("TZ"):
        try:
            return ZoneInfo(configured)
        except (ZoneInfoNotFoundError, ValueError):
            pass  # A POSIX TZ string, or a name this system has no data for.

    # No timezone on purpose: the offset the platform reports for a naive
    # reading is exactly the local offset being asked for.
    observed = datetime.now().astimezone().tzinfo
    return observed if observed is not None else UTC


def _fixed_offset(timezone: str, match: re.Match[str]) -> tzinfo:
    """Return the fixed-offset timezone ``match`` describes."""
    hours = int(match["hours"])
    minutes = int(match["minutes"])
    if hours > _MAX_OFFSET_HOURS or minutes >= _MINUTES_PER_HOUR:
        raise InvalidTimezoneError(timezone)

    offset = timedelta(hours=hours, minutes=minutes)
    if match["sign"] == "-":
        offset = -offset

    try:
        return fixed_offset(offset)
    except ValueError as error:
        raise InvalidTimezoneError(timezone) from error
