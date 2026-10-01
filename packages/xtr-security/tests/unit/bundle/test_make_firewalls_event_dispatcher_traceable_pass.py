"""Every firewall's dispatcher is traced exactly when the event dispatcher bundle traces."""

from __future__ import annotations

import pytest
from xtr_dependency_injection import Kernel
from xtr_event_dispatcher import CompiledEventDispatcher, EventDispatcherInterface
from xtr_event_dispatcher.debug import TraceableEventDispatcher

from tests.fixtures.security_app.bundles import BUNDLES
from xtr_security.bundle import firewall_dispatcher_name

pytestmark = pytest.mark.anyio


def _kernel(*, debug: bool) -> Kernel:
    return Kernel(
        "tests.fixtures.security_app",
        env="test",
        debug=debug,
        bundles=BUNDLES,
        concurrent_scoped_access=True,
    )


async def test_in_debug_mode_a_firewalls_dispatcher_is_traced() -> None:
    async with await _kernel(debug=True).boot() as booted:
        firewall = await booted.container.get(
            EventDispatcherInterface, firewall_dispatcher_name("api")
        )

    assert isinstance(firewall, TraceableEventDispatcher)


async def test_outside_debug_mode_a_firewalls_dispatcher_is_not_traced() -> None:
    async with await _kernel(debug=False).boot() as booted:
        firewall = await booted.container.get(
            EventDispatcherInterface, firewall_dispatcher_name("api")
        )

    assert isinstance(firewall, CompiledEventDispatcher)
