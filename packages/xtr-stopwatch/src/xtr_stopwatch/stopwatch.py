"""Times named events in nested sections, kept apart for every unit of work."""

from __future__ import annotations

from contextvars import ContextVar
from typing import TYPE_CHECKING, Final, final, override

from xtr_clock import MonotonicClock

from .exception import NoStartedSectionError, UnknownSectionError
from .section import Section

if TYPE_CHECKING:
    from xtr_clock import ClockInterface

    from .stopwatch_event import StopwatchEvent

__all__ = ["ROOT", "SECTION_CATEGORY", "SECTION_CHILD_EVENT", "SECTION_EVENT", "Stopwatch"]

ROOT: Final = "__root__"
"""The id the root section is kept under."""

SECTION_EVENT: Final = "__section__"
"""The event spanning a section, started in it as it opens and stopped as it closes."""

SECTION_CHILD_EVENT: Final = "__section__.child"
"""The event spanning a child section, kept in the section that opened it."""

SECTION_CATEGORY: Final = "section"
"""The category of the event spanning a child section."""


@final
class _Activity:
    """What one unit of work timed: its open sections and the ones it stopped.

    Mutated in place, so code run in a copy of the context that made it — a
    synchronous function a worker thread runs — times into the same sections.
    """

    __slots__ = ("sections", "stack")

    def __init__(self, clock: ClockInterface) -> None:
        root = Section(None, clock)
        self.stack: list[Section] = [root]
        self.sections: dict[str, Section] = {ROOT: root}


@final
class Stopwatch:
    """Times what code does, as named events grouped into sections.

    ```python
    stopwatch = Stopwatch()
    stopwatch.open_section()
    stopwatch.start("load", "orm")
    ...
    stopwatch.stop("load")
    stopwatch.stop_section("request-42")
    stopwatch.get_section_events("request-42")["load"].get_duration()
    ```

    An event is started and stopped by name in the current section; a
    section opened inside another nests under it, and is stored under the id
    it is stopped with. Opening a section starts :data:`SECTION_EVENT` in it
    and :data:`SECTION_CHILD_EVENT` in its parent, both stopped as it closes,
    so a section's own duration is one of its events.

    What is timed belongs to the calling context: every concurrent unit of
    work — every request a server handles at once — sees only its own
    sections. :meth:`reset` starts the calling context afresh, which is how a
    unit of work begins with nothing timed.
    """

    __slots__ = ("_activity", "_clock", "detached_variable")

    def __init__(self, clock: ClockInterface | None = None) -> None:
        """Make a stopwatch reading ``clock``.

        Args:
            clock: What time is read from. ``None`` uses a
                :class:`~xtr_clock.MonotonicClock`, because a duration must not
                follow a wall-clock correction.
        """
        self._clock: ClockInterface = clock if clock is not None else MonotonicClock()
        self._activity: ContextVar[_Activity | None] = ContextVar(
            "stopwatch_activity", default=None
        )
        self.detached_variable: tuple[ContextVar[_Activity | None], None] = (self._activity, None)
        """The variable a new connection must start without, and the value it starts from.

        A server may start a connection from a copy of another's context taken
        mid-request; whoever builds the stopwatch for a container registers
        this, so that request's timing never reaches the new one.
        """

    def open_section(self, section_id: str | None = None) -> None:
        """Open a section inside the current one, or reopen the child named ``section_id``.

        Raises:
            UnknownSectionError: When ``section_id`` is given and the current
                section holds no child under it.
        """
        activity = self._current()
        current = activity.stack[-1]
        if section_id is not None and current.get(section_id) is None:
            raise UnknownSectionError(section_id)
        _ = current.start_event(SECTION_CHILD_EVENT, SECTION_CATEGORY)
        activity.stack.append(current.open(section_id))
        _ = activity.stack[-1].start_event(SECTION_EVENT, None)

    def stop_section(self, section_id: str) -> None:
        """Close the current section, storing it under ``section_id``.

        Raises:
            NoStartedSectionError: When only the root section is open.
        """
        activity = self._current()
        if len(activity.stack) == 1:
            raise NoStartedSectionError(section_id)
        _ = activity.stack[-1].stop_event(SECTION_EVENT)
        section = activity.stack.pop().set_id(section_id)
        activity.sections[section_id] = section
        _ = activity.stack[-1].stop_event(SECTION_CHILD_EVENT)

    def start(self, name: str, category: str | None = None) -> StopwatchEvent:
        """Start the event ``name`` in the current section and return it.

        Keep the returned event to stop it: it stays the same object even if
        the context is reset while it runs.
        """
        return self._current().stack[-1].start_event(name, category)

    def stop(self, name: str) -> StopwatchEvent:
        """Stop the event ``name`` in the current section and return it.

        Raises:
            EventNotStartedError: When ``name`` is not running there.
        """
        return self._current().stack[-1].stop_event(name)

    def lap(self, name: str) -> StopwatchEvent:
        """Stop the event ``name`` and start it again at once.

        Raises:
            EventNotStartedError: When ``name`` is not running in the current
                section.
        """
        return self._current().stack[-1].lap_event(name)

    def is_started(self, name: str) -> bool:
        """Tell whether the event ``name`` is running in the current section."""
        return self._current().stack[-1].is_event_started(name)

    def has_open_section(self) -> bool:
        """Tell whether the calling context has a section open, without starting anything.

        A unit of work timing itself opens a section; code that times what it
        does on a shared stopwatch asks this first, so a context nobody times
        in — a worker's own loop, a long command — never accumulates events.
        """
        activity = self._activity.get()
        return activity is not None and len(activity.stack) > 1

    def get_event(self, name: str) -> StopwatchEvent:
        """Return the event ``name`` of the current section.

        Raises:
            UnknownEventError: When the current section never started ``name``.
        """
        return self._current().stack[-1].get_event(name)

    def get_section_events(self, section_id: str) -> dict[str, StopwatchEvent]:
        """Return the events of the section stored as ``section_id``; empty when there is none."""
        section = self._current().sections.get(section_id)
        return section.get_events() if section is not None else {}

    def get_sections(self) -> dict[str, Section]:
        """Return every stopped section by id, the root included."""
        return dict(self._current().sections)

    def reset(self) -> None:
        """Forget everything the calling context timed, and start it afresh.

        Other contexts are left as they are, and an event already handed out
        stays the object it was, so stopping it still closes its period.
        """
        _ = self._activity.set(_Activity(self._clock))

    def _current(self) -> _Activity:
        activity = self._activity.get()
        if activity is None:
            activity = _Activity(self._clock)
            _ = self._activity.set(activity)
        return activity

    @override
    def __repr__(self) -> str:
        """Return how deep the calling context's sections are open."""
        activity = self._activity.get()
        depth = len(activity.stack) - 1 if activity is not None else 0
        return f"{type(self).__name__}(open_sections={depth})"
