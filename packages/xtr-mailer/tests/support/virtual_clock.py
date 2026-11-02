"""A clock whose sleepers wake in time order, as the test moves time on."""

from __future__ import annotations

import heapq
from itertools import count
from typing import TYPE_CHECKING, Self, final

import anyio
from anyio.lowlevel import checkpoint
from xtr_clock import MockClock

if TYPE_CHECKING:
    from datetime import tzinfo

    from xtr_clock import DatePoint

__all__ = ["VirtualClock"]


@final
class VirtualClock:
    """Stands still while tasks sleep on it; :meth:`advance` wakes the earliest sleeper.

    A frozen clock that moves on every sleep cannot tell concurrent sleepers apart: the first
    to sleep moves time for all of them. Here a sleep only waits, and time moves to the next
    wake-up once every task is blocked — so each task resumes at the instant it slept until.
    """

    def __init__(self) -> None:
        self._clock: MockClock = MockClock("2026-01-01 00:00:00")
        self._sleepers: list[tuple[float, int, anyio.Event]] = []
        self._order: count[int] = count()

    def now(self) -> DatePoint:
        return self._clock.now()

    def sleep(self, seconds: float) -> None:
        self._clock.sleep(seconds)

    async def sleep_async(self, seconds: float) -> None:
        if seconds <= 0:
            await checkpoint()
            return
        woken = anyio.Event()
        target = self.now().timestamp() + seconds
        heapq.heappush(self._sleepers, (target, next(self._order), woken))
        await woken.wait()

    def with_timezone(self, timezone: str | tzinfo) -> Self:
        del timezone
        raise NotImplementedError

    async def advance(self) -> bool:
        """Once every task is blocked, move to the earliest wake-up and wake its sleeper.

        Returns whether there was a sleeper to wake.
        """
        await anyio.wait_all_tasks_blocked()
        if not self._sleepers:
            return False
        target, _, woken = heapq.heappop(self._sleepers)
        self._clock.sleep(target - self.now().timestamp())
        woken.set()
        return True
