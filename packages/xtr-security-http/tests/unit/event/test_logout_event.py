"""The event announcing a logout, for the listeners that carry it out."""

from __future__ import annotations

from xtr_event_dispatcher_contracts import event_name_of
from xtr_http_message import HttpFactory
from xtr_security_core.user.in_memory_user import InMemoryUser

from tests.support.messages import make_message
from xtr_security_http.authenticator.token.post_authentication_token import (
    PostAuthenticationToken,
)
from xtr_security_http.event.logout_event import LogoutEvent
from xtr_security_http.security_events import SecurityEvents


def _token() -> PostAuthenticationToken:
    return PostAuthenticationToken(InMemoryUser("ada", roles=()), "main", ())


def test_the_event_carries_the_request_and_the_token() -> None:
    request = make_message()
    token = _token()

    event = LogoutEvent(request, token)

    assert event.get_request() is request
    assert event.get_token() is token


def test_the_event_carries_no_token_when_none_was_authenticated() -> None:
    event = LogoutEvent(make_message(), None)

    assert event.get_token() is None


def test_a_response_set_on_the_event_is_read_back() -> None:
    event = LogoutEvent(make_message(), _token())
    response = HttpFactory().create_response(204)

    event.set_response(response)

    assert event.get_response() is response


def test_the_event_starts_with_no_response() -> None:
    event = LogoutEvent(make_message(), _token())

    assert event.get_response() is None


def test_the_event_is_class_keyed_with_no_name_of_its_own() -> None:
    """The logout runs under its class's qualified name, like the login events."""
    assert SecurityEvents.ALIASES[LogoutEvent] == event_name_of(LogoutEvent)


def test_the_event_names_no_add_cookie_member() -> None:
    """The upstream carrier once grew an ``addCookie``; this one never did."""
    assert not hasattr(LogoutEvent, "add_cookie")
