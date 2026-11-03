"""A date as a queued email carries it: the instant, and the zone it is shown in.

An ISO datetime with its offset keeps the instant, not the zone: read back, a date in
``Europe/Bucharest`` would be one at a fixed ``+02:00``, and in the hour the clocks repeat as
they go back it would compare as another time. A date in a named zone is written as
``2026-10-25T03:30:00+02:00[Europe/Bucharest]`` — the form RFC 9557 gives — and read back in
that zone, the offset telling which of the repeated hours it is. A date at a fixed offset, in
UTC or with none is written as its ISO datetime alone, and read back as it was.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Final
from zoneinfo import ZoneInfo

from ._json import refuse, text

__all__ = ["read_date", "write_date"]

# An ISO datetime, then a zone's name in brackets: words of letters, digits, "_", "+" and "-"
# joined by "/", so the name can never be a path to a file.
_FORM: Final = re.compile(
    r"(?P<instant>[^\[\]]+)(?:\[(?P<zone>[\w+\-]+(?:/[\w+\-]+)*)\])?", re.ASCII
)
# A datetime with microseconds and an offset, and the longest zone names, fit with room.
_LENGTH: Final = 128


def write_date(date: datetime) -> str:
    """Write ``date``, with the name of its zone when it is in a named one."""
    zone = date.tzinfo
    if isinstance(zone, ZoneInfo) and zone.key:
        return f"{date.isoformat()}[{zone.key}]"
    return date.isoformat()


def read_date(data: object, path: str) -> datetime:
    """Read a date :func:`write_date` wrote.

    Raises:
        InvalidArgumentError: It is not one, names a zone this machine does not know, or an
            offset its zone does not have at that time.
    """
    form = _FORM.fullmatch(text(data, path, _LENGTH))
    date = None if form is None else _date(form["instant"], form["zone"])
    if date is None:
        refuse(path, "is not a date: an ISO datetime, then the name of its zone when it has one")
    return date


def _date(instant_text: str, zone_name: str | None) -> datetime | None:
    try:
        instant = datetime.fromisoformat(instant_text)
        if zone_name is None:
            return instant
        offset = instant.utcoffset()
        zoned = instant.astimezone(ZoneInfo(zone_name)) if offset is not None else None
    # A name the zone database lacks, or one of a directory of zones: the error quotes it.
    # An instant in the first or the last year shown in the zone may fall outside them.
    except (ValueError, KeyError, OSError, OverflowError):
        return None
    # Zone rules other than the writer's would show the same instant at another time.
    return zoned if zoned is not None and zoned.utcoffset() == offset else None
