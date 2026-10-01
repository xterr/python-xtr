"""``debug:firewall`` lists the firewalls, or describes one, or reports an unknown."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from xtr_console import Application, CommandTester
from xtr_dependency_injection import Kernel
from xtr_dependency_injection.testing import boot_for_test

from xtr_security.bundle import SecurityBundle

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

pytestmark = pytest.mark.anyio


@pytest.fixture
async def application() -> AsyncIterator[Application]:
    """Boot the served fixture and yield its console application."""
    kernel = Kernel(
        "tests.fixtures.security_app",
        env="test",
        bundles={SecurityBundle: {"all": True}},
    )
    async with await boot_for_test(kernel) as booted:
        yield await booted.container.get(Application)


async def test_it_lists_every_firewall(application: Application) -> None:
    tester = CommandTester(application, "debug:firewall")

    exit_code = await tester.execute()

    assert exit_code == 0
    assert "api" in tester.display
    assert "open" in tester.display


async def test_it_describes_one_firewall(application: Application) -> None:
    tester = CommandTester(application, "debug:firewall")

    exit_code = await tester.execute(["api"])

    assert exit_code == 0
    assert "Entry point" in tester.display
    assert "AccessTokenAuthenticator" in tester.display


async def test_it_reports_an_unknown_firewall(application: Application) -> None:
    tester = CommandTester(application, "debug:firewall")

    exit_code = await tester.execute(["missing"])

    assert exit_code != 0
    assert "missing" in (tester.display + tester.error_display)
