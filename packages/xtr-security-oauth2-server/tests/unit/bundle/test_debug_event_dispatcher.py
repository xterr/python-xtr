"""The listener this package ships is visible to the dispatcher's own debug command.

Every listener here — ours, an application's, an add-on's — is registered
through the event dispatcher rather than wired by hand, so the dispatcher's own
tooling can see it. That is what this asserts: a deployment can find out what
is listening without reading this package's source.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, cast

import pytest
from xtr_console import Application, CommandTester
from xtr_console.bundle import ConsoleBundle
from xtr_dependency_injection import Kernel

from xtr_security_oauth2_server.bundle import OAuth2ServerBundle
from xtr_security_oauth2_server.oauth2_events import OAuth2Events

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

pytestmark = pytest.mark.anyio

#: The one moment this package ships a listener for: the default scopes a
#: deployment configures are applied as a client is stored.
PRE_SAVE_CLIENT = OAuth2Events.PRE_SAVE_CLIENT


def _kernel() -> Kernel:
    """Return a kernel of the in-memory application, with the console active."""
    return Kernel(
        "tests.fixtures.oauth2_server_app",
        env="test",
        debug=True,
        bundles={
            OAuth2ServerBundle: {"all": True},
            ConsoleBundle: {"all": True},
        },
        concurrent_scoped_access=True,
    )


@pytest.fixture
async def tester() -> AsyncIterator[CommandTester]:
    """Boot the application in debug mode and hand over the command."""
    async with await _kernel().boot() as booted:
        yield CommandTester(
            await booted.container.get(Application),
            "debug:event-dispatcher",
        )


async def test_the_bundle_boots_with_the_console_active() -> None:
    async with await _kernel().boot() as booted:
        assert booted.container is not None


async def test_the_moment_a_client_is_stored_is_listed(tester: CommandTester) -> None:
    exit_code = await tester.execute()

    assert exit_code == 0
    assert PRE_SAVE_CLIENT in tester.display


async def test_the_listener_this_package_ships_is_named(tester: CommandTester) -> None:
    exit_code = await tester.execute([PRE_SAVE_CLIENT, "--format", "json"])

    assert exit_code == 0
    listed = cast("dict[str, list[dict[str, object]]]", json.loads(tester.display))
    named = [str(listener.get("callable", "")) for listener in listed[PRE_SAVE_CLIENT]]

    assert any("AddClientDefaultScopesListener" in name for name in named)


async def test_the_listener_is_reached_lazily(tester: CommandTester) -> None:
    # Registered as a service rather than an instance, so a deployment that
    # never stores a client never builds it.
    exit_code = await tester.execute([PRE_SAVE_CLIENT, "--format", "json"])

    assert exit_code == 0
    listed = cast("dict[str, list[dict[str, object]]]", json.loads(tester.display))

    assert "LazyListener" in str(listed[PRE_SAVE_CLIENT][0].get("callable", ""))
