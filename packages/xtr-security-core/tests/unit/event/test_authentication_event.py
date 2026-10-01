"""The authentication events carry the token and share a base."""

from __future__ import annotations

from xtr_event_dispatcher_contracts import Event

from xtr_security_core.authentication.token import NullToken
from xtr_security_core.event import AuthenticationEvent, AuthenticationSuccessEvent


def test_authentication_event_carries_the_token() -> None:
    token = NullToken()
    event = AuthenticationEvent(token)

    assert event.token is token
    assert event.get_authentication_token() is token


def test_success_event_extends_the_base() -> None:
    assert issubclass(AuthenticationSuccessEvent, AuthenticationEvent)
    assert issubclass(AuthenticationEvent, Event)


def test_success_event_reads_the_inherited_token() -> None:
    token = NullToken()
    event = AuthenticationSuccessEvent(token)

    assert event.get_authentication_token() is token
    assert event.is_propagation_stopped() is False
