"""The decoded event carries a mutable payload a listener may mark invalid."""

from __future__ import annotations

from xtr_event_dispatcher_contracts import Event

from xtr_security_jwt.event.jwt_decoded_event import JwtDecodedEvent


def test_it_is_a_dispatcher_event() -> None:
    assert Event in JwtDecodedEvent.__mro__


def test_it_can_be_marked_invalid_and_stops_propagation() -> None:
    event = JwtDecodedEvent({"sub": "ada"})

    assert event.is_valid() is True
    event.mark_as_invalid()

    assert event.is_valid() is False
    assert event.is_propagation_stopped() is True


def test_its_payload_is_mutable() -> None:
    event = JwtDecodedEvent({"sub": "ada"})
    event.set_payload({"sub": "root"})

    assert event.get_payload() == {"sub": "root"}
