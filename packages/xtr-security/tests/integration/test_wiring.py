"""The provider, extractor, hasher and tracing wiring, over a real container.

Boots the wiring fixture — an in-memory provider, a chain over it, a multi-
extractor access-token authenticator, native password hashers and vote tracing —
and runs the firewall over a request event so the paths the served fixtures
leave aside run.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest
from xtr_dependency_injection import Kernel, unit_of_work
from xtr_dependency_injection.testing import boot_for_test
from xtr_http_kernel import RequestEvent
from xtr_password_hasher import UserPasswordHasherInterface
from xtr_security_core import InMemoryUser
from xtr_security_core.authentication.token.storage.token_storage_interface import (
    TokenStorageInterface,
)
from xtr_security_core.authorization.access_decision_manager_interface import (
    AccessDecisionManagerInterface,
)
from xtr_security_core.user.user_provider_interface import UserProviderInterface
from xtr_security_http import (
    CsrfTokenChecker,
    IsGrantedChecker,
    SecurityTokenResolver,
    UserValueResolver,
)
from xtr_security_http.firewall.firewall import Firewall
from xtr_security_http.firewall_map_interface import FirewallMapInterface

from tests.support.messages import make_message
from xtr_security.bundle import SecurityBundle

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from xtr_http_message import ServerRequest
    from xtr_service_contracts import ContainerInterface

pytestmark = pytest.mark.anyio


async def _run(unit: ContainerInterface, message: ServerRequest) -> None:
    """Run the firewall over ``message``, the way the lifecycle's request phase does.

    The firewall resolves the map from the unit the caller opened — the
    request's own, when the lifecycle runs it — and the chain parks what it
    learns on the event's state bag.
    """
    firewall = Firewall(await unit.get(FirewallMapInterface))
    await firewall.on_request(RequestEvent(message, {}))


@pytest.fixture
async def container() -> AsyncIterator[ContainerInterface]:
    kernel = Kernel(
        "tests.fixtures.wiring_app",
        env="test",
        bundles={SecurityBundle: {"all": True}},
        concurrent_scoped_access=True,
    )
    async with await boot_for_test(kernel) as booted:
        yield booted.container


def _message(token: str | None = None) -> ServerRequest:
    headers = {"authorization": f"Bearer {token}"} if token else {}
    return make_message(path="/api/books", headers=headers)


async def test_the_map_answers_the_matched_firewalls_sorted_chain(
    container: ContainerInterface,
) -> None:
    """The chain the configuration parks comes back sorted, with the firewall's listeners."""
    from tests.fixtures.wiring_app.listeners import (
        AheadOfLateListener,
        EarlyListener,
        LateListener,
    )

    async with unit_of_work(container) as unit:
        firewall_map = await unit.get(FirewallMapInterface)
        chain, exception_listener, logout_listener = await firewall_map.get_listeners(
            make_message(path="/open/health"),
        )

    assert [type(listener) for listener in chain] == [
        EarlyListener,
        AheadOfLateListener,
        LateListener,
    ]
    assert exception_listener is None
    assert logout_listener is None


async def test_the_map_carries_the_secured_firewalls_exception_listener(
    container: ContainerInterface,
) -> None:
    """A secured firewall answers with its exception listener and both its own steps."""
    from xtr_security_http import TraceableAuthenticatorManagerListener
    from xtr_security_http.firewall.access_listener import AccessListener
    from xtr_security_http.firewall.exception_listener import ExceptionListener

    async with unit_of_work(container) as unit:
        firewall_map = await unit.get(FirewallMapInterface)
        chain, exception_listener, logout_listener = await firewall_map.get_listeners(
            make_message(path="/api/books"),
        )

    assert [type(listener) for listener in chain] == [
        TraceableAuthenticatorManagerListener,
        AccessListener,
    ]
    assert isinstance(exception_listener, ExceptionListener)
    assert logout_listener is None


async def test_the_chain_provider_resolves(container: ContainerInterface) -> None:
    async with unit_of_work(container) as unit:
        provider = await unit.get(UserProviderInterface, "chain")
        user = await provider.load_user_by_identifier("alice")

    assert user.get_user_identifier() == "alice"


async def test_the_in_memory_provider_resolves(container: ContainerInterface) -> None:
    async with unit_of_work(container) as unit:
        provider = await unit.get(UserProviderInterface, "in_memory")
        user = await provider.load_user_by_identifier("alice")

    assert "ROLE_USER" in user.get_roles()


async def test_the_multi_extractor_authenticator_runs(container: ContainerInterface) -> None:
    async with unit_of_work(container) as unit:
        await _run(unit, _message("good"))
        token = (await unit.get(TokenStorageInterface)).get_token()

    assert token is not None
    assert token.get_user_identifier() == "alice"


async def test_the_user_password_hasher_is_wired(container: ContainerInterface) -> None:
    hasher = await container.get(UserPasswordHasherInterface)
    stored = hasher.hash_password(InMemoryUser("bob"), "s3cret")

    assert hasher.is_password_valid(InMemoryUser("bob", password=stored), "s3cret")


async def test_the_route_marker_services_are_wired(container: ContainerInterface) -> None:
    """The bundle registers the enforcement services the route markers delegate to."""
    async with unit_of_work(container) as unit:
        assert isinstance(await unit.get(UserValueResolver), UserValueResolver)
        assert isinstance(await unit.get(SecurityTokenResolver), SecurityTokenResolver)
        assert isinstance(await unit.get(IsGrantedChecker), IsGrantedChecker)


async def test_the_csrf_checker_is_absent_without_a_token_manager(
    container: ContainerInterface,
) -> None:
    """No token manager wired means no checker: the definition is dropped, not built broken."""
    async with unit_of_work(container) as unit:
        with pytest.raises(LookupError):
            _ = await unit.get(CsrfTokenChecker)


async def test_tracing_logs_each_decision_and_its_votes(container: ContainerInterface) -> None:
    from xtr_security_core import Access, AuthenticatedVoter, TraceableAccessDecisionManager

    async with unit_of_work(container) as unit:
        await _run(unit, _message("good"))
        manager = await unit.get(AccessDecisionManagerInterface)
        assert isinstance(manager, TraceableAccessDecisionManager)
        log = manager.get_decision_log()

    assert len(log) == 1
    assert log[0]["attributes"] == ("IS_AUTHENTICATED",)
    assert all(entry["result"] is True for entry in log)
    first_votes = cast("list[dict[str, object]]", log[0]["voter_details"])
    (detail,) = first_votes
    assert isinstance(detail["voter"], AuthenticatedVoter)
    assert detail["vote"] is Access.GRANTED
    assert detail["reasons"] == ("The user is authenticated.",)
    assert manager.get_strategy() == "affirmative"


async def test_each_unit_of_work_gets_its_own_decision_log(container: ContainerInterface) -> None:
    async with unit_of_work(container) as unit:
        await _run(unit, _message("good"))
        first = await unit.get(AccessDecisionManagerInterface)

    async with unit_of_work(container) as unit:
        second = await unit.get(AccessDecisionManagerInterface)

    assert first is not second


async def test_the_credentials_check_is_wired_with_a_dummy_hasher(
    container: ContainerInterface,
) -> None:
    from xtr_event_dispatcher import EventDispatcher, LazyListener
    from xtr_event_dispatcher_contracts import EventDispatcherInterface
    from xtr_security_http.event.check_passport_event import CheckPassportEvent
    from xtr_security_http.event_listener.check_credentials_listener import (
        CheckCredentialsListener,
    )

    from xtr_security.bundle import firewall_dispatcher_name

    async with unit_of_work(container) as unit:
        dispatcher = cast(
            "EventDispatcher",
            await unit.get(EventDispatcherInterface, firewall_dispatcher_name("api")),
        )
        listeners = [
            await listener.resolve() if isinstance(listener, LazyListener) else listener
            for listener in dispatcher.get_listeners(CheckPassportEvent)
        ]

    checks = [
        owner
        for listener in listeners
        if isinstance((owner := getattr(listener, "__self__", None)), CheckCredentialsListener)
    ]
    assert checks
    assert checks[0]._dummy_hasher is not None
