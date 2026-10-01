"""The created event carries mutable data and header before a token is signed."""

from __future__ import annotations

from xtr_event_dispatcher_contracts import Event
from xtr_security_core.user.in_memory_user import InMemoryUser

from xtr_security_jwt.event.jwt_created_event import JwtCreatedEvent


def test_it_is_a_dispatcher_event() -> None:
    assert Event in JwtCreatedEvent.__mro__


def test_its_data_and_header_are_mutable_and_it_keeps_its_user() -> None:
    user = InMemoryUser("ada")
    event = JwtCreatedEvent({"sub": "ada"}, user)

    event.get_data()["roles"] = ["ROLE_USER"]
    event.set_header({"typ": "at+jwt"})

    assert event.get_data() == {"sub": "ada", "roles": ["ROLE_USER"]}
    assert event.get_header() == {"typ": "at+jwt"}
    assert event.get_user() is user
