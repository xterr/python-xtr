"""Unit tests for :class:`xtr_clock.bundle.ClockBundle`."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
from xtr_dependency_injection import Kernel
from xtr_dependency_injection.testing import assert_zero_config, boot_for_test

from xtr_clock import Clock, ClockInterface, MockClock
from xtr_clock.bundle import ClockBundle

if TYPE_CHECKING:
    from xtr_service_contracts import ContainerInterface

pytestmark = pytest.mark.anyio

APP = "tests.fixtures.app_clock"


async def test_zero_config_boots_and_shuts_down() -> None:
    await assert_zero_config(ClockBundle)


async def test_the_clock_reads_the_system_time_in_the_configured_zone() -> None:
    async with await Kernel(APP).boot() as booted:
        clock = await booted.container.get(ClockInterface)
        now = clock.now()

    assert now.utcoffset() == timedelta(0)
    assert abs(datetime.now(UTC) - now) < timedelta(seconds=5)


async def test_boot_and_shutdown_restore_the_ambient_clock() -> None:
    before = Clock.get()
    async with await Kernel(APP).boot() as booted:
        during = Clock.get()
        built = await booted.container.get(ClockInterface)

    assert during is built
    assert Clock.get() is before


async def test_an_overridden_clock_is_the_one_installed() -> None:
    frozen = Clock(MockClock("2026-01-01 00:00:00"), "UTC")

    async with await boot_for_test(Kernel(APP), overrides={Clock: frozen}) as booted:
        injected = await booted.container.get(ClockInterface)
        ambient = Clock.get()

    assert injected is frozen
    assert ambient is frozen
    assert frozen.now().isoformat() == "2026-01-01T00:00:00+00:00"


async def test_container_interface_and_clock_interface_agree() -> None:
    async with await Kernel(APP).boot() as booted:
        container: ContainerInterface = booted.container
        clock_from_interface = await container.get(ClockInterface)
        clock_from_class = await container.get(Clock)

    assert clock_from_interface is clock_from_class
