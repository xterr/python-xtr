"""A clock that stands still until a test moves it."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Self, final

from .date_point import DatePoint
from .timezone import resolve_timezone

if TYPE_CHECKING:
    from datetime import tzinfo

__all__ = ["MockClock"]


@final
class MockClock:
    """Stands still, and moves only when asked.

    Every reading is the same instant until :meth:`sleep` or :meth:`modify`
    moves it, which is what makes a test about *duration* — a token that
    expires in an hour, a retry that backs off, a report that covers a
    month — finish in no time and give the same answer on every machine, in
    every zone, on the last day of February.

    Time it is told to sleep through passes at once, so a test never waits.

    Where a real clock is built in the machine's own zone, this one defaults
    to UTC: a frozen test should not change its answer because the laptop
    that ran it is somewhere else.
    """

    __slots__ = ("_now",)

    _now: DatePoint

    def __init__(
        self,
        now: datetime | str | None = None,
        timezone: str | tzinfo | None = None,
    ) -> None:
        """Freeze at ``now``.

        Args:
            now: Where to stand still. A datetime freezes exactly there and
                keeps its zone. A string is read by the grammar on
                :mod:`xtr_clock.modifier` against the clock currently in
                force, so ``'+1 day'`` composes with a clock already frozen.
                ``None`` freezes at the current instant.
            timezone: The zone to report in. ``None`` keeps the zone ``now``
                carried, or UTC when it carried none.

        Raises:
            InvalidModifierError: When ``now`` is a string the grammar
                cannot read.
            InvalidTimezoneError: When ``timezone`` names no known zone.
        """
        zone = resolve_timezone(timezone) if timezone is not None else None

        instant = (
            DatePoint.from_datetime(now)
            if isinstance(now, datetime)
            else DatePoint.parse(now if now is not None else "now", zone or UTC)
        )

        self._now = instant.with_timezone(zone) if zone is not None else instant

    @property
    def timezone(self) -> tzinfo:
        """The zone this clock reports its instants in."""
        return self._now.tzinfo if self._now.tzinfo is not None else UTC

    def now(self) -> DatePoint:
        """Return the instant this clock is frozen at.

        The same object every time until the clock moves, which is safe
        because a :class:`~xtr_clock.date_point.DatePoint` is immutable.
        """
        return self._now

    def sleep(self, seconds: float) -> None:
        """Move forward by ``seconds`` at once; zero or less does nothing.

        This is elapsed time, not a wall-clock offset, so sleeping through a
        daylight saving change lands where a real clock would.
        """
        if seconds > 0:
            self._advance(seconds)

    async def sleep_async(self, seconds: float) -> None:
        """Move forward by ``seconds`` at once, yielding to the event loop.

        Nothing is waited for, but control is handed back once so the tasks
        that were waiting on this clock get their turn — which is the whole
        behaviour a test of concurrent code is trying to observe.
        """
        if seconds > 0:
            self._advance(seconds)

        await asyncio.sleep(0)

    def modify(self, modifier: str) -> None:
        """Move to wherever ``modifier`` points, relative to right here.

        Args:
            modifier: A modifier the grammar on :mod:`xtr_clock.modifier`
                can read — an offset, a keyword, or an absolute datetime.

        Raises:
            InvalidModifierError: When the grammar cannot read ``modifier``.
        """
        self._now = self._now.modify(modifier)

    def with_timezone(self, timezone: str | tzinfo) -> Self:
        """Return a clock frozen at this same instant, read in another zone.

        Raises:
            InvalidTimezoneError: When ``timezone`` names no known zone.
        """
        return type(self)(self._now, timezone)

    def _advance(self, seconds: float) -> None:
        """Move the frozen instant forward by an elapsed duration."""
        zone = self._now.tzinfo
        moved = self._now.astimezone(UTC) + timedelta(seconds=seconds)

        self._now = DatePoint.from_datetime(moved.astimezone(zone))

    def __repr__(self) -> str:
        """Return a reading that shows where the clock is frozen."""
        return f"{type(self).__name__}({self._now.isoformat()!r})"
