"""The per-request security state and its key on the bag."""

from __future__ import annotations

from xtr_security_http._security_state import (
    SecurityState,
    security_state_of,
)
from xtr_security_http.security_request_attributes import SecurityRequestAttributes


def test_the_state_is_parked_under_the_prefixed_key() -> None:
    bag: dict[str, object] = {}

    state = security_state_of(bag)

    assert bag[SecurityRequestAttributes.SECURITY_STATE] is state
    assert SecurityRequestAttributes.SECURITY_STATE == "_xtr_security_"


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


def test_a_fresh_state_carries_an_empty_attribute_bag() -> None:
    state = SecurityState()

    assert state.attributes == {}
