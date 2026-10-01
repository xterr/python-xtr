"""The core event names equal the qualified names of their event classes."""

from __future__ import annotations

from xtr_event_dispatcher_contracts import event_name_of

from xtr_security_core import authentication_events
from xtr_security_core.event.authentication_success_event import AuthenticationSuccessEvent
from xtr_security_core.event.vote_event import VoteEvent


def test_each_name_is_the_qualified_name_of_its_event() -> None:
    assert event_name_of(AuthenticationSuccessEvent) == authentication_events.AUTHENTICATION_SUCCESS
    assert event_name_of(VoteEvent) == authentication_events.VOTE
