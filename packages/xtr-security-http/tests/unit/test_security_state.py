"""The per-request security state, its key on the bag, and the carried response."""

from __future__ import annotations

from xtr_http_kernel.bridge import ResponseFactory
from xtr_http_message_contracts import ResponseInterface

from xtr_security_http._security_state import (
    SECURITY_STATE_KEY,
    CarriedResponse,
    SecurityState,
    security_state_of,
)


def test_the_state_is_parked_under_the_prefixed_key() -> None:
    bag: dict[str, object] = {}

    state = security_state_of(bag)

    assert bag[SECURITY_STATE_KEY] is state
    assert SECURITY_STATE_KEY == "_xtr_security_"


def test_the_state_is_created_once_per_bag() -> None:
    bag: dict[str, object] = {}

    first = security_state_of(bag)
    second = security_state_of(bag)

    assert first is second


def test_a_fresh_state_carries_no_firewall_and_no_token() -> None:
    state = SecurityState()

    assert state.authenticated_firewalls == {}
    assert state.firewall_context is None
    assert state.token is None


def test_a_carried_response_holds_its_response() -> None:
    response = ResponseFactory().create_response(200)

    carried = CarriedResponse(response)

    assert carried.response is response
    assert isinstance(carried, Exception)
    assert isinstance(response, ResponseInterface)
