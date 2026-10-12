"""``RequestRefreshTokenEvent`` hands a listener the refresh token that was issued."""

from __future__ import annotations

from xtr_http_message_contracts import ServerRequestInterface

from tests.support.entities import AccessToken, RefreshToken
from tests.support.messages import server_request
from xtr_security_oauth2_server.request_event import RequestEvent
from xtr_security_oauth2_server.request_refresh_token_event import RequestRefreshTokenEvent


def _issued(identifier: str = "the-refresh-token-id") -> RefreshToken:
    token = RefreshToken()
    token.set_identifier(identifier)
    token.set_access_token(AccessToken())
    return token


def _token_request() -> ServerRequestInterface:
    return server_request(
        "POST",
        "https://server.test/token",
        parsed_body={"grant_type": "refresh_token", "refresh_token": "enc.ryp.ted"},
    )


def test_it_carries_the_refresh_token_that_was_issued() -> None:
    issued = _issued()

    event = RequestRefreshTokenEvent(RequestEvent.REFRESH_TOKEN_ISSUED, _token_request(), issued)

    assert event.get_refresh_token() is issued


def test_it_is_a_request_event_like_any_other() -> None:
    request = _token_request()

    event = RequestRefreshTokenEvent(RequestEvent.REFRESH_TOKEN_ISSUED, request, _issued())

    assert isinstance(event, RequestEvent)
    assert event.get_name() == "oauth2_server.refresh_token.issued"
    assert event.get_request() is request


def test_its_repr_shows_nothing_of_the_token_or_the_request() -> None:
    event = RequestRefreshTokenEvent(RequestEvent.REFRESH_TOKEN_ISSUED, _token_request(), _issued())

    shown = repr(event)

    assert shown == "RequestRefreshTokenEvent(name='oauth2_server.refresh_token.issued')"
    assert "the-refresh-token-id" not in shown
    assert "enc.ryp.ted" not in shown
