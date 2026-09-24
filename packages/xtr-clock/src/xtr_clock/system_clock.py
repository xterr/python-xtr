"""A clock that reads the operating system's wall clock."""

from __future__ import annotations

import asyncio
import time
from datetime import datetime
from typing import TYPE_CHECKING, Self, final

from .date_point import DatePoint
from .timezone import local_timezone, resolve_timezone

if TYPE_CHECKING:
    from datetime import tzinfo

__all__ = ["SystemClock"]


@final
class SystemClock:
    """Reads the time the operating system reports.

    This is what an application runs on, and what
    :meth:`~xtr_clock.clock.Clock.get` falls back to when nothing else was
    installed. It follows the wall clock, so it moves when the machine's
    time is corrected — which is what you want for saying *when* something
    happened, and not what you want for measuring *how long* something took.
    Use :class:`~xtr_clock.monotonic_clock.MonotonicClock` for that.
    """

    __slots__ = ("_timezone",)

    _timezone: tzinfo

    def __init__(self, timezone: str | tzinfo | None = None) -> None:
        """Read the clock in ``timezone``, or in the machine's own zone.

        Args:
            timezone: The zone instants are reported in. ``None`` uses the
                zone this machine is configured for.

        Raises:
            InvalidTimezoneError: When ``timezone`` names no known zone.
        """
        self._timezone = resolve_timezone(timezone) if timezone is not None else local_timezone()

    @property
    def timezone(self) -> tzinfo:
        """The zone this clock reports its instants in."""
        return self._timezone

    def now(self) -> DatePoint:
        """Return the current instant."""
        return DatePoint.from_datetime(datetime.now(self._timezone))

    def sleep(self, seconds: float) -> None:
        """Block for ``seconds``; zero or less returns immediately."""
        if seconds > 0:
            time.sleep(seconds)

    async def sleep_async(self, seconds: float) -> None:
        """Wait ``seconds`` without blocking the event loop."""
        await asyncio.sleep(max(seconds, 0.0))

    def with_timezone(self, timezone: str | tzinfo) -> Self:
        """Return the same clock reporting in ``timezone``.

        Raises:
            InvalidTimezoneError: When ``timezone`` names no known zone.
        """
        return type(self)(timezone)

    def __repr__(self) -> str:
        """Return a reading that names the zone, which is all there is to see."""
        return f"{type(self).__name__}({self._timezone!s})"
