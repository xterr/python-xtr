"""The last word on what a token may do, before it is minted."""

from __future__ import annotations

from xtr_event_dispatcher_contracts import Event

from tests.support.models import client_model
from xtr_security_oauth2_server.event.scope_resolve_event import ScopeResolveEvent
from xtr_security_oauth2_server.value_object.grant import Grant
from xtr_security_oauth2_server.value_object.scope import Scope


def _event(user_identifier: str | None = "user-1") -> ScopeResolveEvent:
    return ScopeResolveEvent(
        (Scope("read"), Scope("write")),
        Grant("authorization_code"),
        client_model(),
        user_identifier,
    )


def test_it_is_an_event_the_dispatcher_can_carry() -> None:
    assert isinstance(_event(), Event)


def test_it_carries_the_scopes_settled_so_far() -> None:
    assert _event().get_scopes() == (Scope("read"), Scope("write"))


def test_it_names_the_grant_handing_them_out() -> None:
    assert _event().get_grant() == Grant("authorization_code")


def test_it_names_the_client_asking() -> None:
    assert _event().get_client().get_identifier() == "client-1"


def test_it_names_the_resource_owner_the_token_will_act_for() -> None:
    assert _event().get_user_identifier() == "user-1"


def test_it_names_no_resource_owner_when_the_client_acts_for_itself() -> None:
    assert _event(None).get_user_identifier() is None


def test_a_listener_can_narrow_the_scopes() -> None:
    event = _event()

    _ = event.set_scopes(Scope("read"))

    assert event.get_scopes() == (Scope("read"),)


def test_a_listener_can_take_every_scope_away() -> None:
    event = _event()

    _ = event.set_scopes()

    assert event.get_scopes() == ()


def test_setting_scopes_answers_the_event_so_a_listener_can_chain() -> None:
    event = _event()

    assert event.set_scopes(Scope("read")) is event


def test_its_reading_names_the_grant_and_how_many_scopes_are_left() -> None:
    expected = (
        "ScopeResolveEvent(grant=Grant(grant='authorization_code'), "
        "client=Client(identifier='client-1'), scopes=2)"
    )

    assert repr(_event()) == expected
