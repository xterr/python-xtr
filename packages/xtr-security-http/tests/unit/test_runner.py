"""What the firewall runner skips, what it denies, and what it memoises."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

import pytest
from fastapi.security import HTTPBearer
from xtr_http_foundation import ChainRequestMatcher
from xtr_security_core.authentication.token.storage.token_storage import TokenStorage
from xtr_security_core.authorization import AccessDecisionManager
from xtr_security_core.exception import AccessDeniedError

from tests.support.contexts import FakeFirewallContext
from tests.support.messages import make_message
from xtr_security_http._runner import run_firewall
from xtr_security_http._security_state import SecurityState, security_state_of
from xtr_security_http.access_map import AccessMap
from xtr_security_http.authentication.authenticator_manager_interface import (
    AuthenticatorManagerInterface,
)
from xtr_security_http.firewall.access_listener import AccessListener
from xtr_security_http.firewall_map import FirewallMap

if TYPE_CHECKING:
    from xtr_http_message_contracts import ResponseInterface, ServerRequestInterface

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

    def supports(self, request: ServerRequestInterface, state: SecurityState) -> bool | None:
        del request, state
        return True

    async def authenticate_request(
        self,
        request: ServerRequestInterface,
        state: SecurityState,
    ) -> ResponseInterface | None:
        del request, state
        self.calls += 1
        if self._crash_first and self.calls == 1:
            message = "The authenticator has a bug."
            raise RuntimeError(message)
        return None


def _open_firewall_map() -> FirewallMap:
    context = FakeFirewallContext(
        name="open",
        authenticator_manager=object(),  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        access_listener=object(),  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        scheme=HTTPBearer(auto_error=False),
        security=False,
    )
    return FirewallMap(((ChainRequestMatcher(()), context),))


def _secured_firewall_map(manager: AuthenticatorManagerInterface) -> FirewallMap:
    context = FakeFirewallContext(
        name="api",
        authenticator_manager=manager,
        access_listener=AccessListener(AccessMap(), AccessDecisionManager([])),
        scheme=HTTPBearer(auto_error=False),
    )
    return FirewallMap(((ChainRequestMatcher(()), context),))


async def _run(
    firewall_map: FirewallMap,
    state: SecurityState | None = None,
    *,
    scopes: tuple[str, ...] = (),
) -> SecurityState:
    """Run the firewall over one request's state, returning the state it left."""
    carried = SecurityState() if state is None else state
    await run_firewall(
        None,
        make_message(),
        scopes,
        state=carried,
        firewall_map=firewall_map,
        token_storage=TokenStorage(),
        access_decision_manager=AccessDecisionManager([]),
    )
    return carried


async def test_it_does_nothing_when_no_firewall_matches() -> None:
    _ = await _run(FirewallMap(()))


async def test_a_scope_on_an_unmatched_request_is_denied() -> None:
    with pytest.raises(AccessDeniedError):
        _ = await _run(FirewallMap(()), scopes=("books:write",))


async def test_a_scope_on_an_open_firewall_is_denied() -> None:
    with pytest.raises(AccessDeniedError):
        _ = await _run(_open_firewall_map(), scopes=("books:write",))


def test_the_counting_manager_satisfies_the_manager_interface() -> None:
    assert isinstance(CountingAuthenticatorManager(), AuthenticatorManagerInterface)


async def test_a_crashing_authenticator_is_not_memoised_as_an_authenticated_pass() -> None:
    manager = CountingAuthenticatorManager(crash_first=True)
    firewall_map = _secured_firewall_map(manager)
    state = SecurityState()

    with pytest.raises(RuntimeError):
        _ = await _run(firewall_map, state)
    with pytest.raises(RuntimeError):
        _ = await _run(firewall_map, state)

    assert manager.calls == 1


async def test_a_memoised_failure_is_re_raised_as_a_fresh_instance() -> None:
    manager = CountingAuthenticatorManager(crash_first=True)
    firewall_map = _secured_firewall_map(manager)
    state = SecurityState()

    with pytest.raises(RuntimeError) as first:
        _ = await _run(firewall_map, state)
    with pytest.raises(RuntimeError) as second:
        _ = await _run(firewall_map, state)

    assert second.value is not first.value
    assert type(second.value) is type(first.value)
    assert str(second.value) == str(first.value)


async def test_an_authenticated_pass_is_memoised_so_the_manager_runs_once() -> None:
    manager = CountingAuthenticatorManager()
    firewall_map = _secured_firewall_map(manager)
    state = SecurityState()

    _ = await _run(firewall_map, state)
    _ = await _run(firewall_map, state)

    assert manager.calls == 1


async def test_the_run_records_the_context_and_the_token_on_the_state() -> None:
    firewall_map = _secured_firewall_map(CountingAuthenticatorManager())

    state = await _run(firewall_map)

    assert state.firewall_context is firewall_map.get("api")
    assert state.token is not None


async def test_the_state_is_found_again_from_the_bag_it_was_parked_on() -> None:
    bag: dict[str, object] = {}
    state = security_state_of(bag)
    firewall_map = _secured_firewall_map(CountingAuthenticatorManager())

    _ = await _run(firewall_map, state)

    assert security_state_of(bag) is state
    assert security_state_of(bag).firewall_context is firewall_map.get("api")
