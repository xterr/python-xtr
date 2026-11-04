"""A date as a queued email carries it: the instant, and the zone it is shown in.

An ISO datetime with its offset keeps the instant, not the zone: read back, a date in
``Europe/Bucharest`` would be one at a fixed ``+02:00``, and in the hour the clocks repeat as
they go back it would compare as another time. A date in a named zone is written as
``2026-10-25T03:30:00+02:00[Europe/Bucharest]`` — the form RFC 9557 gives — and read back in
that zone at the wall time written, the offset telling which of the repeated hours it is. A
wall time in the hour the clocks skip as they go forward is read back too, with the offset it
was written with: it is shown as it was, as a direct send would. A date at a fixed offset, in
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
        zone = ZoneInfo(zone_name)
    # A name the zone database lacks, or one of a directory of zones: the error quotes it.
    except (ValueError, KeyError, OSError):
        return None
    offset = instant.utcoffset()
    if offset is None:
        return None
    # The fold whose offset was written; zone rules other than the writer's have none.
    for fold in (0, 1):
        zoned = instant.replace(tzinfo=zone, fold=fold)
        if zoned.utcoffset() == offset:
            return zoned
    return None
