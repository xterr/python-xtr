"""The security bundle honours the zero-config contract and fails a bad build."""

from __future__ import annotations

import pytest
from xtr_dependency_injection import Kernel, unit_of_work
from xtr_dependency_injection.testing import assert_zero_config, boot_for_test
from xtr_security_core import AccessDecisionManagerInterface, TokenStorageInterface

from xtr_security.bundle import SecurityBundle
from xtr_security.firewall_map import FirewallMap

pytestmark = pytest.mark.anyio


async def test_it_builds_and_boots_with_no_configuration() -> None:
    await assert_zero_config(SecurityBundle)


async def test_the_core_services_are_registered_unconfigured() -> None:
    kernel = Kernel(
        "tests.fixtures.security_app",
        env="test",
        bundles={SecurityBundle: {"all": True}},
    )
    async with await boot_for_test(kernel) as booted:
        assert booted.container.has(AccessDecisionManagerInterface)
        assert booted.container.has(TokenStorageInterface)


async def test_the_firewall_map_is_empty_when_no_firewall_is_configured() -> None:
    kernel = Kernel(
        "tests.fixtures.probe_app",
        env="test",
        bundles={SecurityBundle: {"all": True}},
        concurrent_scoped_access=True,
    )
    async with await boot_for_test(kernel) as booted, unit_of_work(booted.container) as unit:
        firewall_map = await unit.get(FirewallMap)

    assert firewall_map.names() == ()
