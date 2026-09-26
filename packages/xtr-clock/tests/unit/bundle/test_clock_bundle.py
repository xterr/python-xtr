"""Unit tests for :class:`xtr_clock.bundle.ClockBundle`."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from xtr_dependency_injection import Kernel
from xtr_dependency_injection.testing import assert_zero_config

from xtr_clock import Clock, ClockInterface
from xtr_clock.bundle import ClockBundle, ClockConfig

if TYPE_CHECKING:
    from xtr_service_contracts import ContainerInterface

pytestmark = pytest.mark.anyio


async def test_zero_config_boots_and_shuts_down() -> None:
    await assert_zero_config(ClockBundle)


async def test_a_mock_clock_returns_the_frozen_instant() -> None:
    kernel = Kernel("tests.fixtures.app_clock", env="test")
    booted = await kernel.boot()
    try:
        clock = await booted.container.get(ClockInterface)
        assert clock.now().isoformat().startswith("2026-01-01T00:00:00")
    finally:
        await booted.shutdown()


def test_frozen_at_without_mock_raises() -> None:
    with pytest.raises(ValueError, match="frozen_at requires mock=True"):
        _ = ClockConfig(frozen_at="2026-01-01 00:00:00")


async def test_boot_and_shutdown_restore_the_ambient_clock() -> None:
    before = Clock.get()
    kernel = Kernel("tests.fixtures.app_clock", env="test")
    booted = await kernel.boot()
    try:
        during = Clock.get()
        assert during is not before
        assert during.now().isoformat().startswith("2026-01-01T00:00:00")
    finally:
        await booted.shutdown()
    assert Clock.get() is before


async def test_container_interface_and_clock_interface_agree() -> None:
    kernel = Kernel("tests.fixtures.app_clock", env="test")
    booted = await kernel.boot()
    try:
        container: ContainerInterface = booted.container
        clock_from_interface = await container.get(ClockInterface)
        clock_from_class = await container.get(Clock)
        assert clock_from_interface is clock_from_class
    finally:
        await booted.shutdown()
