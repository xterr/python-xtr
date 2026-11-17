"""Everything this library raises, under :class:`StopwatchError`."""

from __future__ import annotations

from .event_not_started_error import EventNotStartedError
from .no_started_section_error import NoStartedSectionError
from .stopwatch_error import StopwatchError
from .unknown_event_error import UnknownEventError
from .unknown_section_error import UnknownSectionError

__all__ = [
    "EventNotStartedError",
    "NoStartedSectionError",
    "StopwatchError",
    "UnknownEventError",
    "UnknownSectionError",
]
