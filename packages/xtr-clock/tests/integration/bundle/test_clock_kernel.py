"""End-to-end: an application listing only ClockBundle gets the system clock, overridable."""

from __future__ import annotations

import pytest
from xtr_dependency_injection import Kernel
from xtr_dependency_injection.testing import boot_for_test

from xtr_clock import Clock, ClockInterface, MockClock, now

pytestmark = pytest.mark.anyio


async def test_an_overridden_clock_answers_injected_and_ambient_readers() -> None:
    frozen = Clock(MockClock("2026-01-01 00:00:00"), "UTC")

    kernel = Kernel("tests.fixtures.app_clock")
    async with await boot_for_test(kernel, overrides={Clock: frozen}) as booted:
        injected = (await booted.container.get(ClockInterface)).now().isoformat()
        ambient = now().isoformat()

    assert injected == ambient == "2026-01-01T00:00:00+00:00"
