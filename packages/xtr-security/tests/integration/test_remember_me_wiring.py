"""The remember-me, switch-user, throttling, channel and pre-auth wiring, over a container.

Boots the fixture — a stateful firewall with a form login, a login link, a
remote-user proof, a remember-me cookie, a switch-user block, login
throttling and a channel rule — and reads back what the bundle registered:
the chain in the order it runs (the channel step first, the context step
ahead of the manager, the switch step behind the manager, the access step
after them), the login-success listeners the remember-me flow answers by,
the throttling listener ahead of every passport check, the remember-me
response listener on the main dispatcher, and the generator a page's switch
addresses come from.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest
from xtr_dependency_injection import Kernel, unit_of_work
from xtr_dependency_injection.testing import boot_for_test
from xtr_event_dispatcher import EventDispatcher, LazyListener
from xtr_event_dispatcher_contracts import EventDispatcherInterface
from xtr_http_kernel import ResponseEvent
from xtr_security_http import (
    AccessListener,
    AuthenticatorManagerListener,
    ChannelListener,
    CheckRememberMeConditionsListener,
    ContextListener,
    FormLoginAuthenticator,
    ImpersonateUrlGenerator,
    LoginLinkAuthenticator,
    LoginThrottlingListener,
    RememberMeAuthenticator,
    RememberMeListener,
    RemoteUserAuthenticator,
    ResponseListener,
    SwitchUserListener,
)
from xtr_security_http.authenticator.authenticator_interface import (
    AuthenticatorInterface,
)
from xtr_security_http.authenticator.debug.traceable_authenticator_manager_listener import (
    TraceableAuthenticatorManagerListener,
)
from xtr_security_http.event.check_passport_event import CheckPassportEvent
from xtr_security_http.event.login_success_event import LoginSuccessEvent
from xtr_security_http.firewall.firewall_listener_interface import (
    FirewallListenerInterface,
)

from xtr_security.bundle import SecurityBundle, firewall_dispatcher_name
from xtr_security.bundle.firewall_context import FirewallContext

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from xtr_service_contracts import ContainerInterface

pytestmark = pytest.mark.anyio


@pytest.fixture
async def container() -> AsyncIterator[ContainerInterface]:
    """Boot the fixture the way the kernel boots an application."""
    kernel = Kernel(
        "tests.fixtures.remember_me_app",
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


async def test_the_chain_runs_channel_context_manager_switch_then_access(
    container: ContainerInterface,
) -> None:
    """The channel redirects first; the switch begins from a token only the manager set."""
    async with unit_of_work(container) as unit:
        context = await unit.get(FirewallContext, "main")

    # The tracing pass may swap the manager's step for its traceable variant.
    assert [type(step) for step in context.listeners] in (
        [
            ChannelListener,
            ContextListener,
            AuthenticatorManagerListener,
            SwitchUserListener,
            AccessListener,
        ],
        [
            ChannelListener,
            ContextListener,
            TraceableAuthenticatorManagerListener,
            SwitchUserListener,
            AccessListener,
        ],
    )


async def test_the_login_success_listeners_answer_a_remembered_login(
    container: ContainerInterface,
) -> None:
    """The conditions listener enables the badge ahead of the listener that sets the cookie."""
    async with unit_of_work(container) as unit:
        listeners = await _listeners_of(unit, "main", LoginSuccessEvent)

    types = [type(listener) for listener in listeners]
    assert CheckRememberMeConditionsListener in types
    assert RememberMeListener in types
    # The conditions listener runs first: it enables the badge the set
    # listener reads, so its priority sits above the listener that sets.
    assert types.index(CheckRememberMeConditionsListener) < types.index(RememberMeListener)


async def test_the_throttling_listener_refuses_ahead_of_every_passport_check(
    container: ContainerInterface,
) -> None:
    """The throttling listener runs at 2080, above the provider's own user load."""
    async with unit_of_work(container) as unit:
        listeners = await _listeners_of(unit, "main", CheckPassportEvent)

    # The throttling listener refuses ahead of everything else a passport
    # answers to: the provider's own user load sits far below it.
    assert isinstance(listeners[0], LoginThrottlingListener)
    assert len(listeners) > 1


async def test_the_remember_me_response_listener_answers_the_kernel(
    container: ContainerInterface,
) -> None:
    """One response listener for the application moves the staged cookie out."""
    async with unit_of_work(container) as unit:
        resolved = cast("EventDispatcher", await unit.get(EventDispatcherInterface, None))
        listeners = [
            await listener.resolve() if isinstance(listener, LazyListener) else listener
            for listener in resolved.get_listeners(ResponseEvent)
        ]
        listeners = [getattr(listener, "__self__", listener) for listener in listeners]

    assert any(isinstance(listener, ResponseListener) for listener in listeners)


async def test_the_authenticators_were_registered_by_their_factories(
    container: ContainerInterface,
) -> None:
    """The login link, the remote-user proof and the remembered login all built."""
    async with unit_of_work(container) as unit:
        authenticators = [
            await unit.get(AuthenticatorInterface, f"main#authenticator#{index}")
            for index in range(4)
        ]

    assert [type(authenticator) for authenticator in authenticators] == [
        RemoteUserAuthenticator,
        FormLoginAuthenticator,
        LoginLinkAuthenticator,
        RememberMeAuthenticator,
    ]


async def test_the_impersonate_generator_answers_the_firewalls_switch(
    container: ContainerInterface,
) -> None:
    """The generator resolves, answering the switch-user block the firewall configured."""
    async with unit_of_work(container) as unit:
        generator = await unit.get(ImpersonateUrlGenerator)

    assert isinstance(generator, ImpersonateUrlGenerator)


async def test_the_chain_listener_interface_alias_answers(
    container: ContainerInterface,
) -> None:
    """The switch step is reachable through the interface the chain gathers by."""
    async with unit_of_work(container) as unit:
        step = await unit.get(FirewallListenerInterface, "main#switch_user_listener")

    assert isinstance(step, SwitchUserListener)
