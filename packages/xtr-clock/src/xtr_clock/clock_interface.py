"""What a clock answers to.

Two contracts, because two different things depend on a clock.

:class:`SupportsNow` is the smaller one — a single ``now()`` — and exists so
a clock from somewhere else can be adopted without implementing anything.
:class:`ClockInterface` is what this library's own clocks satisfy and what
application code should ask for, because reading the time is rarely the only
thing a time-sensitive class needs to do with it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, Self, runtime_checkable

if TYPE_CHECKING:
    from datetime import datetime, tzinfo

    from .date_point import DatePoint

__all__ = ["ClockInterface", "SupportsNow"]


@runtime_checkable
class SupportsNow(Protocol):
    """Anything that can say what time it is.

    Deliberately structural and deliberately minimal: a clock written
    against some other library, or a two-line stub in a test, satisfies it
    without importing anything from here. Hand one to
    :class:`~xtr_clock.clock.Clock` to get the full contract back.
    """

    def now(self) -> datetime:
        """Return the current instant."""
        ...


@runtime_checkable
class ClockInterface(SupportsNow, Protocol):
    """The contract time-sensitive code should depend on.

    Depend on this rather than on a concrete clock and the choice between
    reading the operating system, counting monotonically, and standing still
    for a test becomes a constructor argument.

    Both a blocking and an awaitable wait live here rather than on separate
    contracts, because a clock that can only do one of them is a clock half
    the application cannot use — and the two cannot share a name, since one
    returns and the other is awaited.
    """

    def now(self) -> DatePoint:
        """Return the current instant, always timezone-aware."""
        ...

    def sleep(self, seconds: float) -> None:
        """Block for ``seconds``, which a frozen clock does instantly.

        A value of zero or less returns immediately.
        """
        ...

    async def sleep_async(self, seconds: float) -> None:
        """Wait ``seconds`` without blocking the event loop.

        A value of zero or less returns immediately.
        """
        ...

    def with_timezone(self, timezone: str | tzinfo) -> Self:
        """Return the same clock reading its instants in another zone.

        This one is left alone, so a class that pins a zone for itself does
        not change the time anybody else reads.

        Raises:
            InvalidTimezoneError: When ``timezone`` names no known zone.
        """
        ...
