"""``RequestEvent`` is what the server announces as it answers a request."""

from __future__ import annotations

import pytest
from xtr_http_message_contracts import ServerRequestInterface

from tests.support.messages import server_request
from xtr_security_oauth2_server_core.request_event import RequestEvent


def _token_request() -> ServerRequestInterface:
    return server_request(
        "POST",
        "https://server.test/token",
        headers={"Authorization": "Basic YXBwOnMzY3IzdA=="},
    )


def test_it_carries_the_request_it_was_announced_with() -> None:
    request = _token_request()

    event = RequestEvent(RequestEvent.CLIENT_AUTHENTICATION_FAILED, request)

    assert event.get_request() is request


def test_it_carries_the_name_it_was_announced_under() -> None:
    event = RequestEvent(RequestEvent.USER_AUTHENTICATION_FAILED, _token_request())

    assert event.get_name() == "oauth2_server.user.authentication.failed"


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        (
            RequestEvent.CLIENT_AUTHENTICATION_FAILED,
            "oauth2_server.client.authentication.failed",
        ),
        (RequestEvent.USER_AUTHENTICATION_FAILED, "oauth2_server.user.authentication.failed"),
        (
            RequestEvent.REFRESH_TOKEN_CLIENT_FAILED,
            "oauth2_server.refresh_token.client.failed",
        ),
        (RequestEvent.REFRESH_TOKEN_ISSUED, "oauth2_server.refresh_token.issued"),
        (RequestEvent.ACCESS_TOKEN_ISSUED, "oauth2_server.access_token.issued"),
    ],
)
def test_every_name_a_listener_registers_under_carries_the_package_in_front(
    name: str,
    expected: str,
) -> None:
    # The dispatcher is one namespace shared with every other library in the
    # application, so a bare `access_token.issued` would be anyone's.
    assert name == expected


def test_a_listener_can_stop_it() -> None:
    event = RequestEvent(RequestEvent.ACCESS_TOKEN_ISSUED, _token_request())

    event.stop_propagation()

    assert event.is_propagation_stopped()


def test_nobody_has_stopped_it_to_begin_with() -> None:
    event = RequestEvent(RequestEvent.ACCESS_TOKEN_ISSUED, _token_request())

    assert not event.is_propagation_stopped()


def test_its_repr_names_the_event_and_not_what_the_request_carried() -> None:
    event = RequestEvent(RequestEvent.CLIENT_AUTHENTICATION_FAILED, _token_request())

    shown = repr(event)

    assert shown == "RequestEvent(name='oauth2_server.client.authentication.failed')"
    assert "YXBwOnMzY3IzdA==" not in shown
