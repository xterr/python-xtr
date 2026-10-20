"""The stateful wiring, over a real container: the chain, the logout, the back channel.

Boots the stateful fixture — a stateful OIDC firewall with a logout, a
back-channel logout and an end-session listener — and reads back what the
bundle registered: the chain in the order it runs (the context step ahead of
the manager, the refresh listener behind it), the session strategy on the
firewall's dispatcher, the logout step on the context's own slot, the logout
listeners each in their place, and the back-channel handler the application's
route maps.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest
from xtr_dependency_injection import Kernel, unit_of_work
from xtr_dependency_injection.testing import boot_for_test
from xtr_event_dispatcher import EventDispatcher, LazyListener
from xtr_event_dispatcher_contracts import EventDispatcherInterface
from xtr_http_foundation import MemorySessionStorage, SessionStorageInterface
from xtr_security_http import (
    CheckRefreshedUserEvent,
    ContextListener,
    LogoutUrlGenerator,
    OidcBackChannelLogoutListener,
    OidcEndSessionListener,
    OidcTokenRefreshListener,
)
from xtr_security_http.authenticator.debug.traceable_authenticator_manager_listener import (
    TraceableAuthenticatorManagerListener,
)
from xtr_security_http.event.login_success_event import LoginSuccessEvent
from xtr_security_http.event.logout_event import LogoutEvent
from xtr_security_http.event_listener import (
    ClearSiteDataListener,
    CookieClearingListener,
    DefaultLogoutListener,
    SessionLogoutListener,
)
from xtr_security_http.firewall.access_listener import AccessListener
from xtr_security_http.firewall.authenticator_manager_listener import (
    AuthenticatorManagerListener,
)
from xtr_security_http.firewall.logout_listener import LogoutListener

from xtr_security.bundle import SecurityBundle, firewall_dispatcher_name
from xtr_security.bundle.firewall_context import FirewallContext
from xtr_security.oidc_back_channel_logout_handler import OidcBackChannelLogoutHandler

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from xtr_service_contracts import ContainerInterface

pytestmark = pytest.mark.anyio


@pytest.fixture
async def container() -> AsyncIterator[ContainerInterface]:
    """Boot the stateful fixture the way the kernel boots an application."""
    kernel = Kernel(
        "tests.fixtures.stateful_app",
        env="test",
        bundles={SecurityBundle: {"all": True}},
        concurrent_scoped_access=True,
    )
    async with await boot_for_test(kernel) as booted:
        yield booted.container


async def _listeners_of(unit: ContainerInterface, dispatcher: str, event: type) -> list[object]:
    """Return the dispatcher's listeners of ``event``, lazy ones resolved to their owners."""
    resolved = cast(
        "EventDispatcher",
        await unit.get(EventDispatcherInterface, firewall_dispatcher_name(dispatcher)),
    )
    listeners = [
        await listener.resolve() if isinstance(listener, LazyListener) else listener
        for listener in resolved.get_listeners(event)
    ]
    return [getattr(listener, "__self__", listener) for listener in listeners]


async def test_the_chain_runs_the_context_step_ahead_of_the_manager_and_the_refresh(
    container: ContainerInterface,
) -> None:
    """The P4.7 refresh listener is reachable, ordered behind the context step."""
    async with unit_of_work(container) as unit:
        context = await unit.get(FirewallContext, "main")

    # The tracing pass may swap the manager's step for its traceable variant.
    assert [type(step) for step in context.listeners] in (
        [
            ContextListener,
            AuthenticatorManagerListener,
            OidcTokenRefreshListener,
            AccessListener,
        ],
        [
            ContextListener,
            TraceableAuthenticatorManagerListener,
            OidcTokenRefreshListener,
            AccessListener,
        ],
    )
    context_step = context.listeners[0]
    assert isinstance(context_step, ContextListener)
    assert context_step._session_key == "_security.main"


async def test_the_session_strategy_listener_runs_on_the_firewalls_dispatcher(
    container: ContainerInterface,
) -> None:
    """The strategy reaches the firewall's logins as a per-call listener.

    The listener holds the request's own state — the clearable forgery-token
    storage a migration empties — so the dispatcher cannot keep it: it runs
    as a function whose strategy is resolved per call, named after the
    function the bundle places.
    """
    async with unit_of_work(container) as unit:
        listeners = await _listeners_of(unit, "main", LoginSuccessEvent)

    assert any(
        getattr(listener, "__name__", "") == "apply_the_session_strategy" for listener in listeners
    )


async def test_the_logout_step_sits_on_the_contexts_own_slot(
    container: ContainerInterface,
) -> None:
    async with unit_of_work(container) as unit:
        context = await unit.get(FirewallContext, "main")

    assert isinstance(context.logout_listener, LogoutListener)


async def test_the_logout_event_listeners_answer_on_the_firewalls_dispatcher(
    container: ContainerInterface,
) -> None:
    async with unit_of_work(container) as unit:
        listeners = await _listeners_of(unit, "main", LogoutEvent)

    assert [type(listener) for listener in listeners] == [
        OidcEndSessionListener,
        DefaultLogoutListener,
        ClearSiteDataListener,
        SessionLogoutListener,
        CookieClearingListener,
    ]


async def test_the_logout_url_generator_carries_the_firewalls_registration(
    container: ContainerInterface,
) -> None:
    async with unit_of_work(container) as unit:
        generator = await unit.get(LogoutUrlGenerator)

    assert await generator.get_logout_path("main") == "/logout"


async def test_the_back_channel_handler_answers_over_the_ended_sessions(
    container: ContainerInterface,
) -> None:
    async with unit_of_work(container) as unit:
        handler = await unit.get(OidcBackChannelLogoutHandler, "main")

    assert isinstance(handler, OidcBackChannelLogoutHandler)


async def test_the_back_channel_listener_runs_on_the_refreshed_user_check(
    container: ContainerInterface,
) -> None:
    """The plain callable joins the main dispatcher, where the context step announces."""
    async with unit_of_work(container) as unit:
        dispatcher = cast("EventDispatcher", await unit.get(EventDispatcherInterface))
        listeners = [
            await listener.resolve() if isinstance(listener, LazyListener) else listener
            for listener in dispatcher.get_listeners(CheckRefreshedUserEvent)
        ]

    assert [type(listener) for listener in listeners] == [OidcBackChannelLogoutListener]


async def test_the_stateful_firewall_stores_its_sessions_through_the_applications_storage(
    container: ContainerInterface,
) -> None:
    async with unit_of_work(container) as unit:
        storage = await unit.get(SessionStorageInterface)

    assert isinstance(storage, MemorySessionStorage)
