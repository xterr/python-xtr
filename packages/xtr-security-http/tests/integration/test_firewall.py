"""The firewall, its runner, the exception listener and the markers over a real container."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from xtr_dependency_injection import Kernel, unit_of_work
from xtr_dependency_injection.testing import boot_for_test
from xtr_http_kernel import ExceptionEvent
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
from tests.support.requests import make_request
from xtr_security_http._runner import run_firewall
from xtr_security_http._state import FIREWALL_CONTEXT_KEY, CarriedResponse
from xtr_security_http.decorator.current_user import CurrentUser
from xtr_security_http.decorator.is_granted import IsGranted
from xtr_security_http.exception import InvalidAccessTokenError
from xtr_security_http.firewall.exception_listener import ExceptionListener
from xtr_security_http.firewall_map import FirewallMap

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Sequence

    from starlette.requests import Request
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


def _api_request(authorization: str | None = None) -> Request:
    headers = {"authorization": authorization} if authorization else {}
    request = make_request(headers=headers)
    request.scope["path"] = "/api/books"
    return request


async def _run(
    unit: ContainerInterface,
    name: str | None,
    request: Request,
    scopes: Sequence[str] = (),
) -> None:
    """Run the firewall with the services the scheme would inject, resolved from ``unit``."""
    await run_firewall(
        name,
        request,
        scopes,
        firewall_map=await unit.get(FirewallMap),
        token_storage=await unit.get(TokenStorageInterface),
        access_decision_manager=await unit.get(AccessDecisionManagerInterface),
    )


async def _listener(unit: ContainerInterface) -> ExceptionListener:
    return ExceptionListener(await unit.get(AuthenticationTrustResolverInterface))


async def test_run_firewall_authenticates_and_grants(container: ContainerInterface) -> None:
    async with unit_of_work(container) as unit:
        await _run(unit, "api", _api_request("Bearer good"))
        storage = await unit.get(TokenStorageInterface)
        token = storage.get_token()

    assert token is not None
    assert token.get_user_identifier() == "alice"


async def test_run_firewall_denies_a_missing_scope(container: ContainerInterface) -> None:
    async with unit_of_work(container) as unit:
        with pytest.raises(AccessDeniedError):
            await _run(unit, "api", _api_request("Bearer good"), ("reports:write",))


async def test_run_firewall_passes_a_scope_the_token_holds(container: ContainerInterface) -> None:
    async with unit_of_work(container) as unit:
        await _run(unit, "api", _api_request("Bearer good"), ("books:read",))


async def test_run_firewall_raises_on_a_bad_token(container: ContainerInterface) -> None:
    async with unit_of_work(container) as unit:
        with pytest.raises(InvalidAccessTokenError):
            await _run(unit, "api", _api_request("Bearer bad"))


async def test_run_firewall_memoises_authentication(container: ContainerInterface) -> None:
    async with unit_of_work(container) as unit:
        request = _api_request("Bearer bad")
        with pytest.raises(InvalidAccessTokenError):
            await _run(unit, "api", request)
        with pytest.raises(InvalidAccessTokenError):
            await _run(unit, "api", request)


async def test_exception_listener_challenges_an_authentication_error(
    container: ContainerInterface,
) -> None:
    async with unit_of_work(container) as unit:
        request = _api_request()
        firewall_map = await unit.get(FirewallMap)
        setattr(request.state, FIREWALL_CONTEXT_KEY, firewall_map.get("api"))
        event = ExceptionEvent(request, BadCredentialsError())
        await (await _listener(unit)).on_exception(event)

    assert event.response is not None
    assert event.response.status_code == 401


async def test_exception_listener_forbids_a_full_fledged_denial(
    container: ContainerInterface,
) -> None:
    async with unit_of_work(container) as unit:
        request = _api_request("Bearer admin")
        await _run(unit, "api", request)
        error = AccessDeniedError(attributes=("ROLE_SUPERADMIN",))
        event = ExceptionEvent(request, error)
        await (await _listener(unit)).on_exception(event)

    assert event.response is not None
    assert event.response.status_code == 403


async def test_exception_listener_answers_a_scope_denial(container: ContainerInterface) -> None:
    async with unit_of_work(container) as unit:
        request = _api_request("Bearer admin")
        await _run(unit, "api", request)
        error = AccessDeniedError(attributes=("OAUTH2_SCOPE(reports:write)",))
        event = ExceptionEvent(request, error)
        await (await _listener(unit)).on_exception(event)

    assert event.response is not None
    assert event.response.headers["www-authenticate"].startswith("Bearer")


async def test_exception_listener_sends_a_carried_response(container: ContainerInterface) -> None:
    from starlette.responses import JSONResponse  # noqa: PLC0415

    async with unit_of_work(container) as unit:
        response = JSONResponse({"ok": True})
        event = ExceptionEvent(_api_request(), CarriedResponse(response))
        await (await _listener(unit)).on_exception(event)

    assert event.response is response


async def test_is_granted_grants_with_the_current_token(container: ContainerInterface) -> None:
    async with unit_of_work(container) as unit:
        await _run(unit, "api", _api_request("Bearer admin"))
        await IsGranted("ROLE_ADMIN")._decide(
            None,
            await unit.get(TokenStorageInterface),
            await unit.get(AccessDecisionManagerInterface),
        )


async def test_is_granted_denies_without_the_role(container: ContainerInterface) -> None:
    async with unit_of_work(container) as unit:
        await _run(unit, "api", _api_request("Bearer good"))
        with pytest.raises(AccessDeniedError):
            await IsGranted("ROLE_ADMIN")._decide(
                None,
                await unit.get(TokenStorageInterface),
                await unit.get(AccessDecisionManagerInterface),
            )


async def test_current_user_resolves_the_authenticated_user(container: ContainerInterface) -> None:
    async with unit_of_work(container) as unit:
        await _run(unit, "api", _api_request("Bearer good"))
        user = await CurrentUser()._resolve(await unit.get(TokenStorageInterface))

    assert user is not None
    assert user.get_user_identifier() == "alice"
