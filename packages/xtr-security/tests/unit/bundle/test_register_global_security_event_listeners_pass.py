"""The main dispatcher's security listeners reach every firewall's dispatcher, and only those."""

from __future__ import annotations

import pytest
from xtr_dependency_injection import Kernel
from xtr_event_dispatcher import EventDispatcherInterface, LazyListener, Listener
from xtr_security_core.event.vote_event import VoteEvent
from xtr_security_http.event.check_passport_event import CheckPassportEvent
from xtr_security_http.event.login_success_event import LoginSuccessEvent

from tests.fixtures.security_app.bundles import BUNDLES
from xtr_security.bundle import firewall_dispatcher_name

pytestmark = pytest.mark.anyio

_API = firewall_dispatcher_name("api")


def _kernel() -> Kernel:
    return Kernel(
        "tests.fixtures.security_app",
        env="test",
        debug=False,
        bundles=BUNDLES,
        resources=("tests.fixtures.security_app", "tests.fixtures.firewall_listener"),
        concurrent_scoped_access=True,
    )


def _names(listeners: list[Listener]) -> list[str]:
    return [
        listener.method if isinstance(listener, LazyListener) else getattr(listener, "__name__", "")
        for listener in listeners
    ]


async def test_a_main_listener_of_a_security_event_runs_on_the_firewalls_dispatcher() -> None:
    async with await _kernel().boot() as booted:
        firewall = await booted.container.get(EventDispatcherInterface, _API)

        assert "record_check_passport" in _names(firewall.get_listeners(CheckPassportEvent))


async def test_a_main_listener_of_any_other_event_stays_on_the_main_dispatcher() -> None:
    async with await _kernel().boot() as booted:
        main = await booted.container.get(EventDispatcherInterface)
        firewall = await booted.container.get(EventDispatcherInterface, _API)

        assert main.has_listeners(VoteEvent)
        assert not firewall.has_listeners(VoteEvent)


async def test_a_listener_naming_the_firewalls_dispatcher_runs_there_alone() -> None:
    async with await _kernel().boot() as booted:
        main = await booted.container.get(EventDispatcherInterface)
        firewall = await booted.container.get(EventDispatcherInterface, _API)

        assert "on_api_login" in _names(firewall.get_listeners(LoginSuccessEvent))
        assert "on_api_login" not in _names(main.get_listeners(LoginSuccessEvent))


async def test_an_open_firewall_has_no_dispatcher_to_merge_into() -> None:
    async with await _kernel().boot() as booted:
        assert not booted.container.has(EventDispatcherInterface, firewall_dispatcher_name("open"))
