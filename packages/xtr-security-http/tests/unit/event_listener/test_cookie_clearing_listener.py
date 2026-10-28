"""The logout listener that clears the cookies a logout should drop."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from xtr_http_message import HttpFactory

from tests.support.messages import make_message
from xtr_security_http.event.logout_event import LogoutEvent
from xtr_security_http.event_listener import ClearedCookie, CookieClearingListener

pytestmark = pytest.mark.anyio

if TYPE_CHECKING:
    from xtr_http_message_contracts import ResponseInterface


def _event_with(response: ResponseInterface | None = None) -> LogoutEvent:
    """Build a logout event, answered with ``response`` when one is given."""
    event = LogoutEvent(make_message(), None)
    if response is not None:
        event.set_response(response)
    return event


def test_it_subscribes_to_the_logout_event_last() -> None:
    assert CookieClearingListener.get_subscribed_events() == {LogoutEvent: ("on_logout", -255)}


async def test_it_clears_the_configured_cookies_on_the_answered_logout() -> None:
    listener = CookieClearingListener({"session": ClearedCookie()})
    event = _event_with(HttpFactory().create_response(302))

    await listener.on_logout(event)

    response = event.get_response()
    assert response is not None
    (header,) = response.get_header("Set-Cookie")
    assert header.startswith("session=deleted; expires=")
    assert "Max-Age=0" in header
    assert "path=/" in header


async def test_it_repeats_the_path_and_domain_the_cookie_was_set_with() -> None:
    listener = CookieClearingListener(
        {"pref": ClearedCookie(path="/app", domain="example.com", secure=True, samesite="lax")},
    )
    event = _event_with(HttpFactory().create_response(302))

    await listener.on_logout(event)

    response = event.get_response()
    assert response is not None
    (header,) = response.get_header("Set-Cookie")
    assert "path=/app" in header
    assert "domain=example.com" in header
    assert "secure" in header
    assert "samesite=lax" in header


async def test_it_clears_every_configured_cookie_in_order() -> None:
    listener = CookieClearingListener(
        {"first": ClearedCookie(), "second": ClearedCookie(path="/two")},
    )
    event = _event_with(HttpFactory().create_response(302))

    await listener.on_logout(event)

    response = event.get_response()
    assert response is not None
    first, second = response.get_header("Set-Cookie")
    assert first.startswith("first=deleted;")
    assert second.startswith("second=deleted;")
    assert "path=/two" in second


async def test_it_keeps_the_set_cookie_headers_the_response_already_carried() -> None:
    listener = CookieClearingListener({"session": ClearedCookie()})
    answered = HttpFactory().create_response(302).with_header("Set-Cookie", "kept=yes; path=/")
    event = _event_with(answered)

    await listener.on_logout(event)

    response = event.get_response()
    assert response is not None
    kept, cleared = response.get_header("Set-Cookie")
    assert kept == "kept=yes; path=/"
    assert cleared.startswith("session=deleted;")


async def test_a_logout_no_listener_answered_is_left_alone() -> None:
    listener = CookieClearingListener({"session": ClearedCookie()})
    event = _event_with()

    await listener.on_logout(event)

    assert event.get_response() is None


async def test_a_logout_with_no_cookies_configured_touches_nothing() -> None:
    listener = CookieClearingListener({})
    answered = HttpFactory().create_response(302)
    event = _event_with(answered)

    await listener.on_logout(event)

    assert event.get_response() is answered
