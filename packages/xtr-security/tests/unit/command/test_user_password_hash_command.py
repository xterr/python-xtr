"""``security:hash-password`` runs with the factory and user classes the bundle wired."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from xtr_console import Application, CommandTester
from xtr_dependency_injection import Kernel
from xtr_dependency_injection.testing import boot_for_test
from xtr_password_hasher import NativePasswordHasher
from xtr_security_core import InMemoryUser

from xtr_security.bundle import SecurityBundle

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

pytestmark = pytest.mark.anyio


@pytest.fixture
async def application() -> AsyncIterator[Application]:
    """Boot the served fixture, whose hashers map ``InMemoryUser``, and yield its console."""
    kernel = Kernel(
        "tests.fixtures.security_app",
        env="test",
        bundles={SecurityBundle: {"all": True}},
    )
    async with await boot_for_test(kernel) as booted:
        yield await booted.container.get(Application)


async def test_it_hashes_for_the_first_configured_user_class(application: Application) -> None:
    tester = CommandTester(application, "security:hash-password", width=400)

    exit_code = await tester.execute(["secret"], interactive=False)

    assert exit_code == 0
    assert "NativePasswordHasher" in tester.display
    hashed = next(
        line.strip().removeprefix("Password hash: ")
        for line in tester.display.splitlines()
        if "Password hash: " in line
    )
    assert NativePasswordHasher().verify(hashed, "secret")


async def test_it_hashes_for_a_named_user_class(application: Application) -> None:
    tester = CommandTester(application, "security:hash-password", width=400)
    user_class = f"{InMemoryUser.__module__}:{InMemoryUser.__qualname__}"

    exit_code = await tester.execute(["secret", user_class], interactive=False)

    assert exit_code == 0
    assert "NativePasswordHasher" in tester.display
