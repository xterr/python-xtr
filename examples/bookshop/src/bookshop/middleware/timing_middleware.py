"""The ``timing`` / ``stopwatch`` middleware: one class declared under two names."""

from __future__ import annotations

from typing import final

from typing_extensions import override
from xtr_clock import MonotonicClock
from xtr_messenger import Envelope, MiddlewareInterface, StackInterface, as_middleware

from bookshop.stamp.dispatch_time_stamp import DispatchTimeStamp

__all__ = ["TimingMiddleware"]


@final
@as_middleware("timing")
@as_middleware("stopwatch")
class TimingMiddleware(MiddlewareInterface):
    """Stamps how long the rest of the chain took.

    Declared under two names — the decorator is repeatable, and each name reaches the same
    class. Durations come from a monotonic clock.
    """

    def __init__(self) -> None:
        """Measure with a monotonic clock."""
        self._clock = MonotonicClock()

    @override
    async def handle(self, envelope: Envelope, stack: StackInterface, /) -> Envelope:
        started = self._clock.now()
        result = await stack.next().handle(envelope, stack)
        elapsed = (self._clock.now() - started).total_seconds() * 1000
        return result.with_stamps(DispatchTimeStamp(elapsed))
