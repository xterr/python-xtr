"""Every firewall's manager listener is traced exactly when the event dispatcher bundle traces."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from xtr_dependency_injection import Kernel, unit_of_work
from xtr_security_http import (
    AccessListener,
    AuthenticatorManagerListener,
    TraceableAuthenticatorManagerListener,
)
from xtr_security_http.firewall_map_interface import FirewallMapInterface

from tests.fixtures.security_app.bundles import BUNDLES
from tests.support.messages import make_message
from xtr_security.data_collector import SecurityDataCollector

if TYPE_CHECKING:
    from pathlib import Path

    from xtr_service_contracts import ContainerInterface

pytestmark = pytest.mark.anyio

_APP = "tests.fixtures.security_app"


def _kernel(*resources: str, debug: bool) -> Kernel:
    return Kernel(
        _APP,
        env="test",
        debug=debug,
        bundles=BUNDLES,
        resources=(_APP, *resources),
        concurrent_scoped_access=True,
    )


async def _secured_chain(container: ContainerInterface) -> tuple[object, ...]:
    """Return the chain the secured firewall answers, over a request it matches."""
    async with unit_of_work(container) as unit:
        firewall_map = await unit.get(FirewallMapInterface)
        chain, _, _ = await firewall_map.get_listeners(make_message(path="/api/books"))
    return chain


async def test_in_debug_mode_a_firewalls_manager_listener_is_traced() -> None:
    async with await _kernel(debug=True).boot() as booted:
        chain = await _secured_chain(booted.container)

    assert [type(listener) for listener in chain] == [
        TraceableAuthenticatorManagerListener,
        AccessListener,
    ]


async def test_outside_debug_mode_a_firewalls_manager_listener_is_not_traced() -> None:
    async with await _kernel(debug=False).boot() as booted:
        chain = await _secured_chain(booted.container)

    assert [type(listener) for listener in chain] == [
        AuthenticatorManagerListener,
        AccessListener,
    ]


async def test_a_traced_listener_reports_to_the_security_panel_while_profiling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PROFILER_TEST_FOLDER", str(tmp_path))
    async with await _kernel("tests.fixtures.profiler_on", debug=True).boot() as booted:
        collector = await booted.container.get(SecurityDataCollector)
        listener, _ = await _secured_chain(booted.container)

    assert isinstance(listener, TraceableAuthenticatorManagerListener)
    assert listener._recorder == collector.record_authenticator


async def test_a_traced_listener_reports_to_nothing_without_the_profiler() -> None:
    async with await _kernel(debug=True).boot() as booted:
        listener, _ = await _secured_chain(booted.container)

    assert isinstance(listener, TraceableAuthenticatorManagerListener)
    assert listener._recorder is None
