"""The response pass: a staged remember-me cookie moved onto the outgoing head."""

from __future__ import annotations

import pytest
from starlette.datastructures import MutableHeaders
from xtr_http_kernel.event.response_event import ResponseEvent

from tests.support.messages import make_message
from xtr_security_http._security_state import security_state_of
from xtr_security_http.remember_me import RememberMeCookie, ResponseListener
from xtr_security_http.security_request_attributes import SecurityRequestAttributes

pytestmark = pytest.mark.anyio


def _event(*, staged: RememberMeCookie | None = None) -> ResponseEvent:
    """Build a response event whose request's state staged ``staged``, if one did."""
    bag: dict[str, object] = {}
    request = make_message().with_attribute(SecurityRequestAttributes.STATE_BAG, bag)
    if staged is not None:
        security_state_of(bag).attributes[SecurityRequestAttributes.REMEMBER_ME_COOKIE] = staged
    return ResponseEvent(request, bag, 200, MutableHeaders(raw=[]))


def _set_cookies_of(event: ResponseEvent) -> list[str]:
    """Return every ``Set-Cookie`` value the event's head carries."""
    return event.headers.getlist("Set-Cookie")


async def test_a_staged_cookie_is_appended_to_the_outgoing_head() -> None:
    event = _event(staged=RememberMeCookie("REMEMBERME", "the-value"))

    await ResponseListener().on_kernel_response(event)

    assert len(_set_cookies_of(event)) == 1
    assert _set_cookies_of(event)[0].startswith("REMEMBERME=the-value;")


async def test_a_staged_clearing_is_appended_as_the_cleared_form() -> None:
    event = _event(staged=RememberMeCookie("REMEMBERME", None))

    await ResponseListener().on_kernel_response(event)

    assert len(_set_cookies_of(event)) == 1
    assert _set_cookies_of(event)[0].startswith("REMEMBERME=deleted;")


async def test_a_request_that_staged_no_cookie_leaves_the_head_untouched() -> None:
    event = _event()

    await ResponseListener().on_kernel_response(event)

    assert _set_cookies_of(event) == []


def test_the_subscribed_events_listen_to_the_response_event() -> None:
    assert ResponseListener.get_subscribed_events() == {ResponseEvent: "on_kernel_response"}
