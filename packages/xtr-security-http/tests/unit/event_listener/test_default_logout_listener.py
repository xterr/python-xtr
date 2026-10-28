"""The logout listener that answers a logout nothing else answered."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from xtr_http_kernel.bridge import ResponseFactory
from xtr_http_message import HttpFactory

from tests.support.messages import make_message
from xtr_security_http.event.logout_event import LogoutEvent
from xtr_security_http.event_listener import DefaultLogoutListener
from xtr_security_http.http_utils import HttpUtils

pytestmark = pytest.mark.anyio

if TYPE_CHECKING:
    from xtr_http_message_contracts import ResponseInterface


def _listener(target_url: str = "/") -> DefaultLogoutListener:
    return DefaultLogoutListener(HttpUtils(ResponseFactory()), target_url)


def _event_with(response: ResponseInterface | None = None) -> LogoutEvent:
    """Build a logout event, answered with ``response`` when one is given."""
    event = LogoutEvent(make_message(), None)
    if response is not None:
        event.set_response(response)
    return event


def test_it_subscribes_to_the_logout_event_ahead_of_the_clearing_listeners() -> None:
    assert DefaultLogoutListener.get_subscribed_events() == {LogoutEvent: ("on_logout", 64)}


async def test_an_unanswered_logout_is_answered_with_a_redirect_to_the_target() -> None:
    event = _event_with()

    await _listener("/home").on_logout(event)

    response = event.get_response()
    assert response is not None
    assert response.get_status_code() == 302
    assert response.get_header_line("location") == "/home"


async def test_the_target_defaults_to_the_home_path() -> None:
    event = _event_with()

    await _listener().on_logout(event)

    response = event.get_response()
    assert response is not None
    assert response.get_header_line("location") == "/"


async def test_a_logout_a_listener_answered_first_is_left_alone() -> None:
    answered = HttpFactory().create_response(200)
    event = _event_with(answered)

    await _listener("/home").on_logout(event)

    assert event.get_response() is answered
