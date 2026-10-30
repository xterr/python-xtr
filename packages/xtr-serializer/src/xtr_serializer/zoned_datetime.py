"""A datetime that keeps its zone through JSON, the hour repeated as the clocks go back included."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Annotated, Final, TypeAlias
from zoneinfo import ZoneInfo

from pydantic import PlainSerializer, PlainValidator
from pydantic_core import PydanticCustomError

from xtr_serializer._type_names import qualified_name_of
from xtr_serializer.exception import NotNormalizableValueError

__all__ = ["ZonedDateTime"]

# What pydantic and this package call a value that is not a zoned datetime, on either side.
_ERROR_TYPE: Final = "zoned_datetime"

# The written form: an ISO datetime with its offset, then the zone's name in brackets.
_FORM: Final = re.compile(r"(?P<instant>[^\[\]]+)\[(?P<zone>[^\[\]]+)\]")

_READ_REFUSAL: Final = (
    "a zoned datetime is an ISO datetime with its offset, then the name of a known zone in "
    "brackets, the offset being the one the zone has at that time"
)


def _write(value: object) -> str:
    """Write the datetime with its offset, which tells a repeated hour's two times apart."""
    if not isinstance(value, datetime):
        reason = "is not a datetime"
    elif value.tzinfo is None:
        reason = "is naive"
    elif not isinstance(value.tzinfo, ZoneInfo):
        reason = "has a fixed offset, which a plain datetime field keeps"
    elif not value.tzinfo.key:
        reason = "has a zone with no name, read from a file"
    else:
        return f"{value.isoformat()}[{value.tzinfo.key}]"
    raise NotNormalizableValueError(
        f"a zoned datetime must be a datetime in a named ZoneInfo zone; this one {reason}",
        current_type=qualified_name_of(type(value)),
        error_type=_ERROR_TYPE,
    )


def _read(value: object) -> datetime:
    """Read the instant, then show it in the zone, which gives back the wall clock and fold."""
    if isinstance(value, datetime) and isinstance(value.tzinfo, ZoneInfo):
        return value
    form = _FORM.fullmatch(value) if isinstance(value, str) else None
    if form is not None:
        try:
            instant = datetime.fromisoformat(form["instant"])
            zone = ZoneInfo(form["zone"])
            offset = instant.utcoffset()
            zoned = instant.astimezone(zone) if offset is not None else None
        # A name the zone database lacks, a path or a directory of zones: the error quotes it.
        # An instant in the first or the last year shown in the zone may fall outside them.
        except (ValueError, KeyError, OSError, OverflowError):
            pass
        else:
            # Zone rules other than the writer's would show the same instant at another time.
            if zoned is not None and zoned.utcoffset() == offset:
                return zoned
    raise PydanticCustomError(_ERROR_TYPE, _READ_REFUSAL)


ZonedDateTime: TypeAlias = Annotated[
    datetime,
    PlainSerializer(_write, return_type=str, when_used="json"),
    PlainValidator(_read, json_schema_input_type=str),
]
"""A ``datetime`` in a :class:`~zoneinfo.ZoneInfo` zone, read back in that zone.

A plain ``datetime`` field writes an aware datetime with its offset and reads it back with that
offset: the same instant, but the zone's name is gone, and an hour the clocks repeat comes back
compared as another time. Annotate the field with this type and it is written as
``"2026-10-25T03:30:00+02:00[Europe/Bucharest]"`` — the ISO datetime with its offset, then the
zone's name, the form RFC 9557 gives — and read back equal, in the same ``ZoneInfo``, with the same
``fold``. A single string rather than an object, so it stays one JSON value and sorts by its
datetime within a zone.

Writing refuses a naive datetime, one with a fixed offset and one whose zone has no name (read
from a file) with a :class:`~xtr_serializer.NotNormalizableValueError`. Reading refuses text not
in that form, a zone the zone database lacks, an offset the zone does not have at that time —
written under other zone rules than the reader's — and an instant that falls outside the years a
``datetime`` holds once shown in the zone, without quoting the text. A ``datetime`` subclass, such
as a ``DatePoint``, reads back as a ``datetime``.
"""
