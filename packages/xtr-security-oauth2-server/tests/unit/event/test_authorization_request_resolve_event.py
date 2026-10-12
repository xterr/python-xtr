"""The resource owner's decision on an authorization request, or a page asking for it."""

from __future__ import annotations

from xtr_event_dispatcher_contracts import Event
from xtr_http_message import Response

from tests.support.models import client_model
from tests.support.users import SecurityUser
from xtr_security_oauth2_server.entity.client import Client as ClientEntity
from xtr_security_oauth2_server.event.authorization_request_resolve_event import (
    AuthorizationRequestResolveEvent,
)
from xtr_security_oauth2_server.request_types.authorization_request import AuthorizationRequest
from xtr_security_oauth2_server.value_object.scope import Scope


def _authorization_request() -> AuthorizationRequest:
    client = ClientEntity()
    client.set_identifier("client-1")
    client.set_name("Test client")
    client.set_redirect_uri(["https://client.example.com/callback"])
    client.set_confidential(True)

    request = AuthorizationRequest()
    request.set_grant_type_id("authorization_code")
    request.set_client(client)
    request.set_redirect_uri("https://client.example.com/callback")
    request.set_state("opaque-state")
    request.set_code_challenge("a-challenge")
    request.set_code_challenge_method("S256")

    return request


def _event(
    request: AuthorizationRequest | None = None,
) -> AuthorizationRequestResolveEvent:
    return AuthorizationRequestResolveEvent(
        request if request is not None else _authorization_request(),
        (Scope("read"),),
        client_model(),
        SecurityUser(),
    )


def test_it_is_an_event_the_dispatcher_can_carry() -> None:
    assert isinstance(_event(), Event)


def test_a_request_is_denied_until_something_approves_it() -> None:
    assert _event().get_authorization_resolution() is AuthorizationRequestResolveEvent.DENIED


def test_it_carries_an_approval() -> None:
    event = _event()

    _ = event.resolve_authorization(AuthorizationRequestResolveEvent.APPROVED)

    assert event.get_authorization_resolution() is True


def test_resolving_the_request_stops_the_listeners_after_it() -> None:
    event = _event()

    _ = event.resolve_authorization(AuthorizationRequestResolveEvent.APPROVED)

    assert event.is_propagation_stopped() is True


def test_no_response_is_set_until_a_listener_sets_one() -> None:
    assert _event().get_response() is None


def test_it_carries_the_response_a_listener_set() -> None:
    event = _event()
    response = Response(200, None, b"consent form")

    _ = event.set_response(response)

    assert event.get_response() is response


def test_setting_a_response_stops_the_listeners_after_it() -> None:
    event = _event()

    _ = event.set_response(Response())

    assert event.is_propagation_stopped() is True


def test_resolving_the_request_drops_a_response_set_earlier() -> None:
    event = _event()
    _ = event.set_response(Response())

    _ = event.resolve_authorization(AuthorizationRequestResolveEvent.APPROVED)

    assert event.get_response() is None


def test_it_names_the_grant_the_request_is_for() -> None:
    assert _event().get_grant_type_id() == "authorization_code"


def test_it_names_the_client_asking() -> None:
    assert _event().get_client().get_identifier() == "client-1"


def test_it_carries_the_scopes_asked_for() -> None:
    assert _event().get_scopes() == (Scope("read"),)


def test_it_carries_the_resource_owner_the_request_is_shown_to() -> None:
    user = SecurityUser("someone")
    event = AuthorizationRequestResolveEvent(
        _authorization_request(),
        (),
        client_model(),
        user,
    )

    assert event.get_user() is user


def test_a_listener_can_put_another_resource_owner_on_it() -> None:
    event = _event()
    other = SecurityUser("someone-else")

    _ = event.set_user(other)

    assert event.get_user() is other


def test_it_reports_the_approval_the_request_itself_already_carries() -> None:
    request = _authorization_request()
    request.set_authorization_approved(True)

    assert _event(request).is_authorization_approved() is True


def test_it_reports_the_redirect_uri_the_request_named() -> None:
    assert _event().get_redirect_uri() == "https://client.example.com/callback"


def test_it_reports_the_state_the_request_carried() -> None:
    assert _event().get_state() == "opaque-state"


def test_it_reports_the_code_challenge_the_request_carried() -> None:
    assert _event().get_code_challenge() == "a-challenge"


def test_it_reports_how_that_challenge_was_derived() -> None:
    assert _event().get_code_challenge_method() == "S256"


def test_its_setters_answer_the_event_so_a_listener_can_chain_them() -> None:
    event = _event()

    assert event.set_user(SecurityUser()) is event
    assert event.resolve_authorization(AuthorizationRequestResolveEvent.APPROVED) is event
    assert event.set_response(Response()) is event


def test_its_reading_holds_neither_the_state_nor_the_code_challenge() -> None:
    reading = repr(_event())

    assert "opaque-state" not in reading
    assert "a-challenge" not in reading
    assert reading == (
        "AuthorizationRequestResolveEvent(client=Client(identifier='client-1'), "
        "resolution=False, response=False)"
    )
