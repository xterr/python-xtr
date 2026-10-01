"""The authenticated event carries the verified payload and the security token."""

from __future__ import annotations

from xtr_event_dispatcher_contracts import Event
from xtr_security_core.authentication.token.null_token import NullToken

from xtr_security_jwt.event.jwt_authenticated_event import JwtAuthenticatedEvent


def test_it_is_a_dispatcher_event() -> None:
    assert Event in JwtAuthenticatedEvent.__mro__


def test_it_carries_payload_and_token_and_its_payload_is_mutable() -> None:
    token = NullToken()
    event = JwtAuthenticatedEvent({"sub": "ada"}, token)

    assert event.get_payload() == {"sub": "ada"}
    assert event.get_token() is token
    event.set_payload({"sub": "root"})
    assert event.get_payload() == {"sub": "root"}
