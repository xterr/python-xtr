"""The event announcing a user switch, into an impersonation or out of one."""

from __future__ import annotations

import pytest
from xtr_event_dispatcher_contracts import Event
from xtr_security_core.user.in_memory_user import InMemoryUser

from tests.support.messages import make_message
from xtr_security_http.authenticator.token.post_authentication_token import (
    PostAuthenticationToken,
)
from xtr_security_http.event.switch_user_event import SwitchUserEvent

pytestmark = pytest.mark.anyio


def test_a_switch_event_carries_the_request_and_the_target_user() -> None:
    request = make_message(path="/admin")
    target = InMemoryUser("ada")

    event = SwitchUserEvent(request, target)

    assert isinstance(event, Event)
    assert event.get_request() is request
    assert event.get_target_user() is target


def test_a_switch_event_starts_with_no_token_until_one_is_set() -> None:
    event = SwitchUserEvent(make_message(), InMemoryUser("ada"))

    assert event.get_token() is None


def test_a_listener_may_replace_the_token_the_switch_settles_on() -> None:
    event = SwitchUserEvent(make_message(), InMemoryUser("ada"))
    replacement = PostAuthenticationToken(InMemoryUser("grace"), "main", ())

    event.set_token(replacement)

    assert event.get_token() is replacement
