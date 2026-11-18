"""A group of events sharing one origin, nested in the section that opened it."""

from __future__ import annotations

from typing import TYPE_CHECKING, Self, final, override

from xtr_clock import MonotonicClock

from ._milliseconds import now_ms
from .exception import EventNotStartedError, UnknownEventError
from .stopwatch_event import StopwatchEvent

if TYPE_CHECKING:
    from xtr_clock import ClockInterface

__all__ = ["Section"]


@final
class Section:
    """Holds the events timed while it was the current section.

    A section measures every event it holds from one origin — the instant it
    was opened — so its events line up on one timeline. The root section has
    no origin of its own; each of its events is measured from the instant it
    first started.
    """

    __slots__ = ("_children", "_clock", "_events", "_id", "_origin")

    def __init__(self, origin: float | None = None, clock: ClockInterface | None = None) -> None:
        """Make a section measuring its events from ``origin``.

        Args:
            origin: The instant the section began, in milliseconds since the
                epoch; ``None`` for the root.
            clock: What time is read from. ``None`` uses a
                :class:`~xtr_clock.MonotonicClock`.
        """
        self._origin = origin
        self._clock: ClockInterface = clock if clock is not None else MonotonicClock()
        self._id: str | None = None
        self._children: list[Section] = []
        self._events: dict[str, StopwatchEvent] = {}

    @property
    def id(self) -> str | None:
        """The id the section was stopped under, or ``None`` while it runs."""
        return self._id

    def set_id(self, section_id: str) -> Self:
        """Name the section ``section_id``."""
        self._id = section_id
        return self

    @property
    def children(self) -> tuple[Section, ...]:
        """The sections opened inside this one, in the order they opened."""
        return tuple(self._children)

    def get(self, section_id: str) -> Section | None:
        """Return the child named ``section_id``, or ``None``."""
        for child in self._children:
            if child.id == section_id:
                return child
        return None

    def open(self, section_id: str | None) -> Section:
        """Return the child named ``section_id``, opening a new one when there is none."""
        child = self.get(section_id) if section_id is not None else None
        if child is None:
            child = Section(now_ms(self._clock), self._clock)
            self._children.append(child)
        return child

    def start_event(self, name: str, category: str | None) -> StopwatchEvent:
        """Start ``name`` here, making the event the first time it is started."""
        event = self._events.get(name)
        if event is None:
            origin = self._origin if self._origin is not None else now_ms(self._clock)
            event = StopwatchEvent(origin, category, name, self._clock)
            self._events[name] = event
        return event.start()

    def is_event_started(self, name: str) -> bool:
        """Tell whether ``name`` has an open period here."""
        event = self._events.get(name)
        return event is not None and event.is_started()

    def stop_event(self, name: str) -> StopwatchEvent:
        """Stop ``name`` here.

        Raises:
            EventNotStartedError: When this section never started ``name``,
                or it is not running.
        """
        event = self._events.get(name)
        if event is None:
            raise EventNotStartedError(name)
        return event.stop()

    def lap_event(self, name: str) -> StopwatchEvent:
        """Stop ``name`` and start it again at once.

        Raises:
            EventNotStartedError: When ``name`` is not running here.
        """
        return self.stop_event(name).start()

    def get_event(self, name: str) -> StopwatchEvent:
        """Return the event ``name``.

        Raises:
            UnknownEventError: When this section never started ``name``.
        """
        event = self._events.get(name)
        if event is None:
            raise UnknownEventError(name)
        return event

    def get_events(self) -> dict[str, StopwatchEvent]:
        """Return every event of this section by name, in the order each first started."""
        return dict(self._events)

    @override
    def __repr__(self) -> str:
        """Return the section's id and how many events and children it holds."""
        return (
            f"{type(self).__name__}(id={self._id!r}, events={len(self._events)}, "
            f"children={len(self._children)})"
        )
