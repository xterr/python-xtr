"""A named thing being timed, made of every period it ran for."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, Self, final, override

from xtr_clock import MonotonicClock

from ._milliseconds import now_ms
from .exception import EventNotStartedError
from .stopwatch_period import StopwatchPeriod

if TYPE_CHECKING:
    from xtr_clock import ClockInterface

__all__ = ["StopwatchEvent"]

_DEFAULT_CATEGORY: Final = "default"


@final
class StopwatchEvent:
    """Times one named thing, however many times it runs.

    Each :meth:`start` opens a period and the matching :meth:`stop` closes
    it, so a listener called three times is one event with three periods
    rather than three events. Starts nest: a start while already running opens
    a second period, and stops close them last-opened first.

    Every reading is in milliseconds from :attr:`origin` — the instant the
    event's section began — so the events of a section share one axis and can
    be drawn on one timeline.
    """

    __slots__ = ("_category", "_clock", "_name", "_origin", "_periods", "_started")

    def __init__(
        self,
        origin: float,
        category: str | None = None,
        name: str | None = None,
        clock: ClockInterface | None = None,
    ) -> None:
        """Make an event measured from ``origin``.

        Args:
            origin: The instant readings are measured from, in milliseconds
                since the epoch.
            category: What kind of work this is, grouping events on a
                timeline; ``"default"`` when not given.
            name: What the event is called, for errors and for plain data.
            clock: What time is read from. ``None`` uses a
                :class:`~xtr_clock.MonotonicClock`, because a duration must not
                follow a wall-clock correction.
        """
        self._origin = origin
        self._category = category or _DEFAULT_CATEGORY
        self._name = name or "unknown"
        self._clock: ClockInterface = clock if clock is not None else MonotonicClock()
        self._started: list[float] = []
        self._periods: list[StopwatchPeriod] = []

    @property
    def name(self) -> str:
        """What the event is called."""
        return self._name

    @property
    def category(self) -> str:
        """What kind of work the event times."""
        return self._category

    @property
    def origin(self) -> float:
        """The instant readings are measured from, in milliseconds since the epoch."""
        return self._origin

    def start(self) -> Self:
        """Open a period now."""
        self._started.append(self._now())
        return self

    def stop(self) -> Self:
        """Close the period opened last.

        Raises:
            EventNotStartedError: When no period is open.
        """
        if not self._started:
            raise EventNotStartedError(self._name)
        self._periods.append(StopwatchPeriod(self._started.pop(), self._now()))
        return self

    def lap(self) -> Self:
        """Close the open period and open the next one at the same instant.

        Raises:
            EventNotStartedError: When no period is open.
        """
        return self.stop().start()

    def is_started(self) -> bool:
        """Tell whether a period is open."""
        return bool(self._started)

    def ensure_stopped(self) -> None:
        """Close every open period."""
        while self._started:
            _ = self.stop()

    def get_periods(self) -> tuple[StopwatchPeriod, ...]:
        """Return every closed period, in the order they closed."""
        return tuple(self._periods)

    def get_start_time(self) -> float:
        """Return when the event first began, in milliseconds from the origin.

        The first closed period's start, or the first open one's when none has
        closed yet; ``0.0`` for an event that never started.
        """
        if self._periods:
            return self._periods[0].start
        return self._started[0] if self._started else 0.0

    def get_end_time(self) -> float:
        """Return when the last closed period ended, in milliseconds from the origin."""
        return self._periods[-1].end if self._periods else 0.0

    def get_duration(self) -> float:
        """Return the time spent in every period, open ones up to now, in milliseconds."""
        closed = sum(period.duration for period in self._periods)
        if not self._started:
            return closed
        now = self._now()
        return closed + sum(now - start for start in self._started)

    def to_dict(self) -> dict[str, object]:
        """Return the event as plain data, readable once serialised to JSON."""
        return {
            "name": self._name,
            "category": self._category,
            "origin": self._origin,
            "start": self.get_start_time(),
            "end": self.get_end_time(),
            "duration": self.get_duration(),
            "periods": [period.to_dict() for period in self._periods],
        }

    def _now(self) -> float:
        return now_ms(self._clock) - self._origin

    @override
    def __repr__(self) -> str:
        """Return the event's name, category and duration so far."""
        return (
            f"{type(self).__name__}({self._name!r}, category={self._category!r}, "
            f"duration={self.get_duration():.3f})"
        )
