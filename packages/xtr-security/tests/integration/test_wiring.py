"""The provider, extractor, hasher and tracing wiring, over a real container.

Boots the wiring fixture — an in-memory provider, a chain over it, a multi-
extractor access-token authenticator, native password hashers and vote tracing —
and drives ``run_firewall`` so the paths the served fixtures leave aside run.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest
from xtr_dependency_injection import Kernel, unit_of_work
from xtr_dependency_injection.testing import boot_for_test
from xtr_password_hasher import UserPasswordHasherInterface
from xtr_security_core import InMemoryUser
from xtr_security_core.authentication.token.storage.token_storage_interface import (
    TokenStorageInterface,
)
from xtr_security_core.authorization.access_decision_manager_interface import (
    AccessDecisionManagerInterface,
)
from xtr_security_core.user.user_provider_interface import UserProviderInterface
from xtr_security_http._runner import run_firewall
from xtr_security_http.firewall_map_interface import FirewallMapInterface

from xtr_security.bundle import SecurityBundle

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Sequence

    from starlette.requests import Request
    from xtr_service_contracts import ContainerInterface

pytestmark = pytest.mark.anyio


async def _run(unit: ContainerInterface, request: Request, scopes: Sequence[str] = ()) -> None:
    await run_firewall(
        "api",
        request,
        scopes,
        firewall_map=await unit.get(FirewallMapInterface),
        token_storage=await unit.get(TokenStorageInterface),
        access_decision_manager=await unit.get(AccessDecisionManagerInterface),
    )


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


def _request(token: str | None = None) -> Request:
    from starlette.requests import Request

    headers = [(b"authorization", f"Bearer {token}".encode())] if token else []
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/books",
        "headers": headers,
        "query_string": b"",
        "server": ("test", 80),
        "scheme": "http",
        "client": ("1.2.3.4", 1),
    }
    return Request(scope)


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
        await _run(unit, _request("good"))
        token = (await unit.get(TokenStorageInterface)).get_token()

    assert token is not None
    assert token.get_user_identifier() == "alice"


async def test_the_user_password_hasher_is_wired(container: ContainerInterface) -> None:
    hasher = await container.get(UserPasswordHasherInterface)
    stored = hasher.hash_password(InMemoryUser("bob"), "s3cret")

    assert hasher.is_password_valid(InMemoryUser("bob", password=stored), "s3cret")


async def test_tracing_dispatches_a_vote_event(container: ContainerInterface) -> None:
    async with unit_of_work(container) as unit:
        await _run(unit, _request("good"), ("books:read",))


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
