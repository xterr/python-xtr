"""End-to-end: an application listing only ClockBundle gets a frozen clock."""

from __future__ import annotations

import pytest
from xtr_dependency_injection import Kernel

from xtr_clock import ClockInterface

pytestmark = pytest.mark.anyio


async def test_the_app_clock_reports_the_configured_instant() -> None:
    kernel = Kernel("tests.fixtures.app_clock", env="test")
    booted = await kernel.boot()
    try:
        clock = await booted.container.get(ClockInterface)
        assert clock.now().isoformat() == "2026-01-01T00:00:00+00:00"
    finally:
        await booted.shutdown()
