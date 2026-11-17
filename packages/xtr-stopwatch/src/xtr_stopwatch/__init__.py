"""Times what code does: named events, grouped by category, nested in sections.

A profile wants to know where a request spent its time — which listener,
which query, which template — and on one axis, so the pieces can be drawn
as a timeline. :class:`~xtr_stopwatch.stopwatch.Stopwatch` records exactly
that: each event is a name, a category and the periods it ran for, and every
event of a section is measured from the section's own origin.

What is timed belongs to the calling context, so concurrent requests served
by one process each see only their own events.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from .exception import (
    EventNotStartedError,
    NoStartedSectionError,
    StopwatchError,
    UnknownEventError,
    UnknownSectionError,
)
from .section import Section
from .stopwatch import ROOT, SECTION_CATEGORY, SECTION_CHILD_EVENT, SECTION_EVENT, Stopwatch
from .stopwatch_event import StopwatchEvent
from .stopwatch_period import StopwatchPeriod

try:
    __version__ = version("xtr-stopwatch")
except PackageNotFoundError:  # pragma: no cover
    # Running from a source tree or a vendored copy, with no installed
    # metadata to read. Having no version is better than refusing to import.
    __version__ = "0+unknown"

__all__ = [
    "ROOT",
    "SECTION_CATEGORY",
    "SECTION_CHILD_EVENT",
    "SECTION_EVENT",
    "EventNotStartedError",
    "NoStartedSectionError",
    "Section",
    "Stopwatch",
    "StopwatchError",
    "StopwatchEvent",
    "StopwatchPeriod",
    "UnknownEventError",
    "UnknownSectionError",
    "__version__",
]
