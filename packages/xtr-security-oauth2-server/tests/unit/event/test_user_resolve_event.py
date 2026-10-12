"""The one event that carries a resource owner's own credentials."""

from __future__ import annotations

from xtr_event_dispatcher_contracts import Event

from tests.support.models import client_model
from tests.support.users import SecurityUser
from xtr_security_oauth2_server.event.user_resolve_event import UserResolveEvent
from xtr_security_oauth2_server.value_object.grant import Grant


def _event() -> UserResolveEvent:
    return UserResolveEvent("someone", "s3cret", Grant("password"), client_model())


def test_it_is_an_event_the_dispatcher_can_carry() -> None:
    assert isinstance(_event(), Event)


def test_it_carries_the_name_the_request_sent() -> None:
    assert _event().get_username() == "someone"


def test_it_carries_the_password_the_request_sent() -> None:
    assert _event().get_password() == "s3cret"


def test_it_names_the_grant_asking() -> None:
    assert _event().get_grant() == Grant("password")


def test_it_names_the_client_asking() -> None:
    assert _event().get_client().get_identifier() == "client-1"


def test_no_user_is_resolved_until_a_listener_resolves_one() -> None:
    assert _event().get_user() is None


def test_it_carries_the_user_a_listener_resolved() -> None:
    event = _event()
    user = SecurityUser()

    _ = event.set_user(user)

    assert event.get_user() is user


def test_a_listener_can_take_a_resolved_user_back_off() -> None:
    event = _event()
    _ = event.set_user(SecurityUser())

    _ = event.set_user(None)

    assert event.get_user() is None


def test_resolving_a_user_answers_the_event_so_a_listener_can_chain() -> None:
    event = _event()

    assert event.set_user(SecurityUser()) is event


def test_its_reading_holds_neither_the_password_nor_the_name() -> None:
    reading = repr(_event())

    assert "s3cret" not in reading
    assert "someone" not in reading
    assert reading == "UserResolveEvent(grant=Grant(grant='password'), resolved=False)"
