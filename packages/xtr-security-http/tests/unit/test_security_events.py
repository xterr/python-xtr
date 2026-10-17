"""The security event names, and the class each name belongs to."""

from __future__ import annotations

from xtr_event_dispatcher_contracts import Event, event_name_of

from xtr_security_http.event import (
    AuthenticationTokenCreatedEvent,
    CheckPassportEvent,
    LoginFailureEvent,
    LoginSuccessEvent,
)
from xtr_security_http.security_events import SecurityEvents


def test_the_named_events_carry_their_documented_names() -> None:
    assert SecurityEvents.INTERACTIVE_LOGIN == "security.interactive_login"
    assert SecurityEvents.SWITCH_USER == "security.switch_user"


def test_every_event_class_maps_to_the_name_it_dispatches_under() -> None:
    aliases = SecurityEvents.ALIASES

    assert set(aliases) == {
        AuthenticationTokenCreatedEvent,
        CheckPassportEvent,
        LoginFailureEvent,
        LoginSuccessEvent,
    }
    for event_class, name in aliases.items():
        assert issubclass(event_class, Event)
        assert name == event_name_of(event_class)
