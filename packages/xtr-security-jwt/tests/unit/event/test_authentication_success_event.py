"""The authentication-success event carries a mutable data mapping and its user."""

from __future__ import annotations

from xtr_event_dispatcher_contracts import Event
from xtr_security_core.user.in_memory_user import InMemoryUser

from xtr_security_jwt.event.authentication_success_event import AuthenticationSuccessEvent


def test_it_is_a_dispatcher_event() -> None:
    assert Event in AuthenticationSuccessEvent.__mro__


def test_its_data_is_mutable_and_it_keeps_its_user() -> None:
    user = InMemoryUser("ada")
    event = AuthenticationSuccessEvent({"token": "t"}, user)

    event.set_data({"token": "t", "extra": 1})

    assert event.get_data() == {"token": "t", "extra": 1}
    assert event.get_user() is user
