"""The logout listener that clears the browser's site data."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from xtr_http_message import HttpFactory

from tests.support.messages import make_message
from xtr_security_http.event.logout_event import LogoutEvent
from xtr_security_http.event_listener import ClearSiteDataListener

pytestmark = pytest.mark.anyio

if TYPE_CHECKING:
    from xtr_http_message_contracts import ResponseInterface


def _event_with(response: ResponseInterface | None = None) -> LogoutEvent:
    """Build a logout event, answered with ``response`` when one is given."""
    event = LogoutEvent(make_message(), None)
    if response is not None:
        event.set_response(response)
    return event


def test_it_subscribes_to_the_logout_event_at_the_default_priority() -> None:
    assert ClearSiteDataListener.get_subscribed_events() == {LogoutEvent: "on_logout"}


async def test_it_sets_the_site_data_header_on_the_answered_logout() -> None:
    listener = ClearSiteDataListener(("cache", "storage"))
    event = _event_with(HttpFactory().create_response(302))

    await listener.on_logout(event)

    response = event.get_response()
    assert response is not None
    assert response.get_header_line("Clear-Site-Data") == '"cache", "storage"'


async def test_it_quotes_the_catch_all_directive() -> None:
    listener = ClearSiteDataListener(("*",))
    event = _event_with(HttpFactory().create_response(302))

    await listener.on_logout(event)

    response = event.get_response()
    assert response is not None
    assert response.get_header_line("Clear-Site-Data") == '"*"'


async def test_it_leaves_a_response_that_already_carries_the_header_alone() -> None:
    listener = ClearSiteDataListener(("cache",))
    answered = HttpFactory().create_response(302).with_header("Clear-Site-Data", '"cookies"')
    event = _event_with(answered)

    await listener.on_logout(event)

    assert event.get_response() is answered
    assert answered.get_header_line("Clear-Site-Data") == '"cookies"'


async def test_a_logout_no_listener_answered_is_left_alone() -> None:
    listener = ClearSiteDataListener(("*",))
    event = _event_with()

    await listener.on_logout(event)

    assert event.get_response() is None
