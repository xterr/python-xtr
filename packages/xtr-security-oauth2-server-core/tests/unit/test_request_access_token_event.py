"""``RequestAccessTokenEvent`` hands a listener the access token that was issued."""

from __future__ import annotations

from xtr_http_message_contracts import ServerRequestInterface

from tests.support.entities import AccessToken
from tests.support.messages import server_request
from xtr_security_oauth2_server_core.request_access_token_event import RequestAccessTokenEvent
from xtr_security_oauth2_server_core.request_event import RequestEvent


def _issued(identifier: str = "the-access-token-id") -> AccessToken:
    token = AccessToken()
    token.set_identifier(identifier)
    return token


def _token_request() -> ServerRequestInterface:
    return server_request(
        "POST",
        "https://server.test/token",
        headers={"Authorization": "Basic YXBwOnMzY3IzdA=="},
    )


def test_it_carries_the_access_token_that_was_issued() -> None:
    issued = _issued()

    event = RequestAccessTokenEvent(RequestEvent.ACCESS_TOKEN_ISSUED, _token_request(), issued)

    assert event.get_access_token() is issued


def test_it_is_a_request_event_like_any_other() -> None:
    request = _token_request()

    event = RequestAccessTokenEvent(RequestEvent.ACCESS_TOKEN_ISSUED, request, _issued())

    assert isinstance(event, RequestEvent)
    assert event.get_name() == "oauth2_server.access_token.issued"
    assert event.get_request() is request


def test_a_listener_can_stop_it() -> None:
    event = RequestAccessTokenEvent(RequestEvent.ACCESS_TOKEN_ISSUED, _token_request(), _issued())

    event.stop_propagation()

    assert event.is_propagation_stopped()


def test_its_repr_shows_nothing_of_the_token_or_the_request() -> None:
    event = RequestAccessTokenEvent(RequestEvent.ACCESS_TOKEN_ISSUED, _token_request(), _issued())

    shown = repr(event)

    assert shown == "RequestAccessTokenEvent(name='oauth2_server.access_token.issued')"
    assert "the-access-token-id" not in shown
    assert "YXBwOnMzY3IzdA==" not in shown
