"""The firewall, its runner, the exception listener and the markers over a real container."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from xtr_dependency_injection import Kernel, unit_of_work
from xtr_dependency_injection.testing import boot_for_test
from xtr_http_kernel import ExceptionEvent
from xtr_http_kernel.bridge import ResponseFactory, StarletteHttpFactory
from xtr_security_core.authentication.authentication_trust_resolver_interface import (
    AuthenticationTrustResolverInterface,
)
from xtr_security_core.authentication.token.storage.token_storage_interface import (
    TokenStorageInterface,
)
from xtr_security_core.authorization.access_decision_manager_interface import (
    AccessDecisionManagerInterface,
)
from xtr_security_core.exception import AccessDeniedError, BadCredentialsError

from tests.fixtures.security_app.bundle import SecurityFixtureBundle
from tests.support.messages import make_message
from xtr_security_http._runner import run_firewall
from xtr_security_http._security_state import CarriedResponse, security_state_of
from xtr_security_http.decorator.current_user import CurrentUser
from xtr_security_http.decorator.is_granted import IsGranted
from xtr_security_http.firewall.exception_listener import ExceptionListener
from xtr_security_http.firewall_map import FirewallMap

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, MutableMapping, Sequence

    from xtr_http_message_contracts import ServerRequestInterface
    from xtr_service_contracts import ContainerInterface

pytestmark = pytest.mark.anyio


@pytest.fixture
async def container() -> AsyncIterator[ContainerInterface]:
    kernel = Kernel(
        "tests.fixtures.security_app",
        env="test",
        bundles={SecurityFixtureBundle: {"all": True}},
    )
    async with await boot_for_test(kernel) as booted:
        yield booted.container


def _api_message(authorization: str | None = None) -> ServerRequestInterface:
    headers = {"authorization": authorization} if authorization else None
    return make_message(path="/api/books", headers=headers)


def _state_bag() -> MutableMapping[str, object]:
    """Return the state bag a request carries, empty as a request begins."""
    return {}


async def _run(
    unit: ContainerInterface,
    name: str | None,
    message: ServerRequestInterface,
    scopes: Sequence[str] = (),
    bag: MutableMapping[str, object] | None = None,
) -> MutableMapping[str, object]:
    """Run the firewall with the services the scheme would inject, resolved from ``unit``.

    Returns the request's state bag, carrying what the run left on it.
    """
    carried: MutableMapping[str, object] = {} if bag is None else bag
    await run_firewall(
        name,
        message,
        tuple(scopes),
        state=security_state_of(carried),
        firewall_map=await unit.get(FirewallMap),
        token_storage=await unit.get(TokenStorageInterface),
        access_decision_manager=await unit.get(AccessDecisionManagerInterface),
    )
    return carried


async def _listener(unit: ContainerInterface) -> ExceptionListener:
    return ExceptionListener(
        await unit.get(AuthenticationTrustResolverInterface),
        ResponseFactory(),
        StarletteHttpFactory(),
    )


async def test_run_firewall_authenticates_and_grants(container: ContainerInterface) -> None:
    async with unit_of_work(container) as unit:
        _ = await _run(unit, "api", _api_message("Bearer good"))
        storage = await unit.get(TokenStorageInterface)
        token = storage.get_token()

    assert token is not None
    assert token.get_user_identifier() == "alice"


async def test_run_firewall_denies_a_missing_scope(container: ContainerInterface) -> None:
    async with unit_of_work(container) as unit:
        with pytest.raises(AccessDeniedError):
            _ = await _run(unit, "api", _api_message("Bearer good"), ("reports:write",))


async def test_run_firewall_passes_a_scope_the_token_holds(container: ContainerInterface) -> None:
    async with unit_of_work(container) as unit:
        _ = await _run(unit, "api", _api_message("Bearer good"), ("books:read",))


async def test_run_firewall_denies_a_bad_token_through_the_access_decision(
    container: ContainerInterface,
) -> None:
    async with unit_of_work(container) as unit:
        # The manager answers the failure without raising; the request goes on
        # anonymous, and it is the access decision that denies.
        with pytest.raises(AccessDeniedError):
            _ = await _run(unit, "api", _api_message("Bearer bad"))


async def test_run_firewall_memoises_authentication(container: ContainerInterface) -> None:
    async with unit_of_work(container) as unit:
        bag = _state_bag()
        with pytest.raises(AccessDeniedError):
            _ = await _run(unit, "api", _api_message("Bearer bad"), bag=bag)
        with pytest.raises(AccessDeniedError):
            _ = await _run(unit, "api", _api_message("Bearer bad"), bag=bag)

        # Both passes found the failure settled: the memo records an
        # anonymous pass, not an error to re-raise.
        assert security_state_of(bag).authenticated_firewalls == {"api": None}


async def test_exception_listener_challenges_an_authentication_error(
    container: ContainerInterface,
) -> None:
    async with unit_of_work(container) as unit:
        firewall_map = await unit.get(FirewallMap)
        bag = _state_bag()
        security_state_of(bag).firewall_context = firewall_map.get("api")
        event = ExceptionEvent(_api_message(), bag, BadCredentialsError())
        await (await _listener(unit)).on_exception(event)

    assert event.response is not None
    assert event.response.status_code == 401


async def test_exception_listener_forbids_a_full_fledged_denial(
    container: ContainerInterface,
) -> None:
    async with unit_of_work(container) as unit:
        bag = _state_bag()
        _ = await _run(unit, "api", _api_message("Bearer admin"), bag=bag)
        error = AccessDeniedError(attributes=("ROLE_SUPERADMIN",))
        event = ExceptionEvent(_api_message(), bag, error)
        await (await _listener(unit)).on_exception(event)

    assert event.response is not None
    assert event.response.status_code == 403


async def test_exception_listener_answers_a_scope_denial(container: ContainerInterface) -> None:
    async with unit_of_work(container) as unit:
        bag = _state_bag()
        _ = await _run(unit, "api", _api_message("Bearer admin"), bag=bag)
        error = AccessDeniedError(attributes=("OAUTH2_SCOPE(reports:write)",))
        event = ExceptionEvent(_api_message(), bag, error)
        await (await _listener(unit)).on_exception(event)

    assert event.response is not None
    assert event.response.headers["www-authenticate"].startswith("Bearer")


async def test_exception_listener_sends_a_carried_response(container: ContainerInterface) -> None:
    async with unit_of_work(container) as unit:
        response = ResponseFactory().create_response(200)
        event = ExceptionEvent(_api_message(), {}, CarriedResponse(response))
        await (await _listener(unit)).on_exception(event)

    assert event.response is response


async def test_is_granted_grants_with_the_current_token(container: ContainerInterface) -> None:
    async with unit_of_work(container) as unit:
        _ = await _run(unit, "api", _api_message("Bearer admin"))
        await IsGranted("ROLE_ADMIN")._decide(
            None,
            await unit.get(TokenStorageInterface),
            await unit.get(AccessDecisionManagerInterface),
        )


async def test_is_granted_denies_without_the_role(container: ContainerInterface) -> None:
    async with unit_of_work(container) as unit:
        _ = await _run(unit, "api", _api_message("Bearer good"))
        with pytest.raises(AccessDeniedError):
            await IsGranted("ROLE_ADMIN")._decide(
                None,
                await unit.get(TokenStorageInterface),
                await unit.get(AccessDecisionManagerInterface),
            )


async def test_current_user_resolves_the_authenticated_user(container: ContainerInterface) -> None:
    async with unit_of_work(container) as unit:
        _ = await _run(unit, "api", _api_message("Bearer good"))
        user = await CurrentUser()._resolve(await unit.get(TokenStorageInterface))

    assert user is not None
    assert user.get_user_identifier() == "alice"
