"""A token response is built, and a listener may replace it before it is sent."""

from __future__ import annotations

from xtr_event_dispatcher_contracts import Event
from xtr_http_message import Response

from xtr_security_oauth2_server.event.token_request_resolve_event import TokenRequestResolveEvent


def test_it_is_an_event_the_dispatcher_can_carry() -> None:
    assert isinstance(TokenRequestResolveEvent(Response()), Event)


def test_it_carries_the_response_about_to_be_sent() -> None:
    response = Response(200, None, b"{}")

    assert TokenRequestResolveEvent(response).get_response() is response


def test_a_listener_can_put_another_response_on_it() -> None:
    event = TokenRequestResolveEvent(Response())
    replacement = Response().with_status(418)

    _ = event.set_response(replacement)

    assert event.get_response() is replacement


def test_setting_a_response_answers_the_event_so_a_listener_can_chain() -> None:
    event = TokenRequestResolveEvent(Response())

    assert event.set_response(Response()) is event


def test_its_reading_holds_no_token_from_the_body() -> None:
    event = TokenRequestResolveEvent(Response(200, None, b'{"access_token": "secret"}'))

    assert "secret" not in repr(event)
