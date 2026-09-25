"""A clock that counts forward, whatever the wall clock does."""

from __future__ import annotations

import asyncio
import time
from copy import copy
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Final, Self, final

from .date_point import DatePoint
from .timezone import local_timezone, resolve_timezone

if TYPE_CHECKING:
    from datetime import tzinfo

__all__ = ["MonotonicClock"]

_EPOCH: Final = datetime(1970, 1, 1, tzinfo=UTC)
_NANOSECONDS_PER_MICROSECOND: Final = 1000


@final
class MonotonicClock:
    """Counts from a counter that only ever moves forward.

    A wall clock can jump: a daylight saving change, an administrator, a
    time daemon correcting a drift. Subtracting two readings taken either
    side of one of those gives a duration that is wrong, and occasionally
    negative. This clock is anchored to the wall clock once, when it is
    built, and from then on reports that anchor plus however much the
    machine's monotonic counter has advanced.

    Use it for measuring elapsed time — a timeout, a rate limit, a span in a
    profile. Use :class:`~xtr_clock.system_clock.SystemClock` for recording
    when something happened, since this one drifts from the wall clock by
    exactly whatever correction it refused to follow.
    """

    __slots__ = ("_anchor_ns", "_timezone")

    _anchor_ns: int
    _timezone: tzinfo

    def __init__(self, timezone: str | tzinfo | None = None) -> None:
        """Anchor to the wall clock now, then count from the monotonic one.

        Args:
            timezone: The zone instants are reported in. ``None`` uses the
                zone this machine is configured for.

        Raises:
            InvalidTimezoneError: When ``timezone`` names no known zone.
        """
        self._anchor_ns = time.time_ns() - time.monotonic_ns()
        self._timezone = resolve_timezone(timezone) if timezone is not None else local_timezone()

    @property
    def timezone(self) -> tzinfo:
        """The zone this clock reports its instants in."""
        return self._timezone

    def now(self) -> DatePoint:
        """Return the current instant, truncated to the microsecond."""
        elapsed = self._anchor_ns + time.monotonic_ns()
        moment = _EPOCH + timedelta(microseconds=elapsed // _NANOSECONDS_PER_MICROSECOND)

        return DatePoint.from_datetime(moment.astimezone(self._timezone))

    def sleep(self, seconds: float) -> None:
        """Block for ``seconds``; zero or less returns immediately."""
        if seconds > 0:
            time.sleep(seconds)

    async def sleep_async(self, seconds: float) -> None:
        """Wait ``seconds`` without blocking the event loop."""
        await asyncio.sleep(max(seconds, 0.0))

    def with_timezone(self, timezone: str | tzinfo) -> Self:
        """Return the same clock reporting in ``timezone``.

        The anchor is carried over rather than taken again, so the copy and
        the original never disagree about what time it is.

        Raises:
            InvalidTimezoneError: When ``timezone`` names no known zone.
        """
        clone = copy(self)
        # Reaching into the copy rather than rebuilding: the constructor would
        # take a fresh anchor, and the two clocks would then disagree.
        clone._timezone = resolve_timezone(timezone)  # noqa: SLF001

        return clone

    def __repr__(self) -> str:
        """Return a reading that names the zone, which is all there is to see."""
        return f"{type(self).__name__}({self._timezone!s})"
