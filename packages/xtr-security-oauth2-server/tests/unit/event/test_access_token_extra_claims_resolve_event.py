"""The claims an application wants carried in an access token, before it is signed."""

from __future__ import annotations

from xtr_event_dispatcher_contracts import Event

from xtr_security_oauth2_server.entity.client import Client
from xtr_security_oauth2_server.entity.scope import Scope
from xtr_security_oauth2_server.event.access_token_extra_claims_resolve_event import (
    AccessTokenExtraClaimsResolveEvent,
)


def _client_entity() -> Client:
    client = Client()
    client.set_identifier("client-1")
    client.set_name("Test client")
    client.set_redirect_uri([])
    client.set_confidential(True)

    return client


def _scope_entity(identifier: str) -> Scope:
    scope = Scope()
    scope.set_identifier(identifier)

    return scope


def _event(user_identifier: str | None = "user-1") -> AccessTokenExtraClaimsResolveEvent:
    return AccessTokenExtraClaimsResolveEvent(
        _client_entity(),
        (_scope_entity("read"),),
        user_identifier,
    )


def test_it_is_an_event_the_dispatcher_can_carry() -> None:
    assert isinstance(_event(), Event)


def test_it_names_the_client_the_token_is_for() -> None:
    assert _event().get_client().get_identifier() == "client-1"


def test_it_carries_the_scopes_the_token_was_granted() -> None:
    assert [str(scope) for scope in _event().get_scopes()] == ["read"]


def test_it_names_the_resource_owner_the_token_acts_for() -> None:
    assert _event().get_user_identifier() == "user-1"


def test_it_names_no_resource_owner_when_the_client_acts_for_itself() -> None:
    assert _event(None).get_user_identifier() is None


def test_no_extra_claim_is_asked_for_until_a_listener_asks() -> None:
    assert _event().get_extra_claims() == {}


def test_it_carries_the_claims_a_listener_asked_for() -> None:
    event = _event()

    _ = event.set_extra_claims({"tenant": "acme"})

    assert event.get_extra_claims() == {"tenant": "acme"}


def test_the_claims_it_carries_cannot_be_changed_through_the_mapping_given() -> None:
    event = _event()
    asked = {"tenant": "acme"}
    _ = event.set_extra_claims(asked)

    asked["tenant"] = "other"

    assert event.get_extra_claims() == {"tenant": "acme"}


def test_setting_claims_answers_the_event_so_a_listener_can_chain() -> None:
    event = _event()

    assert event.set_extra_claims({}) is event


def test_its_reading_holds_no_claim_value() -> None:
    event = _event()
    _ = event.set_extra_claims({"tenant": "acme"})

    reading = repr(event)

    assert "acme" not in reading
    assert "tenant" in reading
