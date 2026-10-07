"""What the firewall runner skips, what it denies, and what it memoises."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

import pytest
from fastapi.security import HTTPBearer
from xtr_security_core.authentication.token.storage.token_storage import TokenStorage
from xtr_security_core.authorization import AccessDecisionManager
from xtr_security_core.exception import AccessDeniedError

from tests.support.contexts import FakeFirewallContext
from tests.support.requests import make_request
from xtr_security_http._runner import run_firewall
from xtr_security_http.access_map import AccessMap
from xtr_security_http.authentication.authenticator_manager_interface import (
    AuthenticatorManagerInterface,
)
from xtr_security_http.firewall.access_listener import AccessListener
from xtr_security_http.firewall_map import FirewallMap
from xtr_security_http.request_matcher.chain_request_matcher import ChainRequestMatcher

if TYPE_CHECKING:
    from fastapi.security.base import SecurityBase
    from starlette.requests import Request
    from starlette.responses import Response

pytestmark = pytest.mark.anyio


@final
class CountingAuthenticatorManager:
    """Counts the passes it is asked for, crashing on the first when told to.

    A crash stands in for an authenticator with a bug: what it raises is no
    authentication failure, so nothing downstream turns it into a challenge.
    """

    def __init__(self, *, crash_first: bool = False) -> None:
        self.calls = 0
        self._crash_first = crash_first

    def supports(self, request: Request) -> bool | None:
        del request
        return True

    async def authenticate_request(self, request: Request) -> Response | None:
        del request
        self.calls += 1
        if self._crash_first and self.calls == 1:
            message = "The authenticator has a bug."
            raise RuntimeError(message)
        return None


def _open_firewall_map() -> FirewallMap:
    scheme: SecurityBase = HTTPBearer(auto_error=False)
    context = FakeFirewallContext(
        name="open",
        authenticator_manager=object(),  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        access_listener=object(),  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        scheme=scheme,
        security=False,
    )
    return FirewallMap(((ChainRequestMatcher(()), context),))


def _secured_firewall_map(manager: AuthenticatorManagerInterface) -> FirewallMap:
    scheme: SecurityBase = HTTPBearer(auto_error=False)
    context = FakeFirewallContext(
        name="api",
        authenticator_manager=manager,
        access_listener=AccessListener(AccessMap(), AccessDecisionManager([])),
        scheme=scheme,
    )
    return FirewallMap(((ChainRequestMatcher(()), context),))


async def _run(firewall_map: FirewallMap, request: Request) -> None:
    await run_firewall(
        None,
        request,
        (),
        firewall_map=firewall_map,
        token_storage=TokenStorage(),
        access_decision_manager=AccessDecisionManager([]),
    )


async def test_it_does_nothing_when_no_firewall_matches() -> None:
    await run_firewall(
        None,
        make_request(),
        (),
        firewall_map=FirewallMap(()),
        token_storage=TokenStorage(),
        access_decision_manager=AccessDecisionManager([]),
    )


async def test_a_scope_on_an_unmatched_request_is_denied() -> None:
    with pytest.raises(AccessDeniedError):
        await run_firewall(
            None,
            make_request(),
            ("books:write",),
            firewall_map=FirewallMap(()),
            token_storage=TokenStorage(),
            access_decision_manager=AccessDecisionManager([]),
        )


async def test_a_scope_on_an_open_firewall_is_denied() -> None:
    with pytest.raises(AccessDeniedError):
        await run_firewall(
            None,
            make_request(),
            ("books:write",),
            firewall_map=_open_firewall_map(),
            token_storage=TokenStorage(),
            access_decision_manager=AccessDecisionManager([]),
        )


def test_the_counting_manager_satisfies_the_manager_interface() -> None:
    assert isinstance(CountingAuthenticatorManager(), AuthenticatorManagerInterface)


async def test_a_crashing_authenticator_is_not_memoised_as_an_authenticated_pass() -> None:
    manager = CountingAuthenticatorManager(crash_first=True)
    firewall_map = _secured_firewall_map(manager)
    request = make_request()
    with pytest.raises(RuntimeError):
        await _run(firewall_map, request)

    with pytest.raises(RuntimeError):
        await _run(firewall_map, request)

    assert manager.calls == 1


async def test_a_memoised_failure_is_re_raised_as_a_fresh_instance() -> None:
    manager = CountingAuthenticatorManager(crash_first=True)
    firewall_map = _secured_firewall_map(manager)
    request = make_request()
    with pytest.raises(RuntimeError) as first:
        await _run(firewall_map, request)
    with pytest.raises(RuntimeError) as second:
        await _run(firewall_map, request)

    assert second.value is not first.value
    assert type(second.value) is type(first.value)
    assert str(second.value) == str(first.value)


async def test_an_authenticated_pass_is_memoised_so_the_manager_runs_once() -> None:
    manager = CountingAuthenticatorManager()
    firewall_map = _secured_firewall_map(manager)
    request = make_request()

    await _run(firewall_map, request)
    await _run(firewall_map, request)

    assert manager.calls == 1
