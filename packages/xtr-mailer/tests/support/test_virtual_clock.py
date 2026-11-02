from __future__ import annotations

import anyio
import pytest
from xtr_clock import ClockInterface

from tests.support.virtual_clock import VirtualClock

pytestmark = pytest.mark.anyio


def test_it_is_a_clock() -> None:
    assert isinstance(VirtualClock(), ClockInterface)


async def test_concurrent_sleepers_wake_at_the_instant_each_slept_until() -> None:
    clock = VirtualClock()
    start = clock.now().timestamp()
    woke: dict[str, float] = {}

    async def sleeper(name: str, seconds: float) -> None:
        await clock.sleep_async(seconds)
        woke[name] = clock.now().timestamp() - start

    async with anyio.create_task_group() as group:
        _ = group.start_soon(sleeper, "late", 2)
        _ = group.start_soon(sleeper, "early", 0.5)
        _ = group.start_soon(sleeper, "now", 0)
        while await clock.advance():
            pass

    assert woke == {"now": 0, "early": 0.5, "late": 2}


async def test_advance_reports_when_nobody_sleeps() -> None:
    assert not await VirtualClock().advance()


def test_a_blocking_sleep_moves_it_on() -> None:
    clock = VirtualClock()
    start = clock.now().timestamp()

    clock.sleep(3)

    assert clock.now().timestamp() - start == 3
