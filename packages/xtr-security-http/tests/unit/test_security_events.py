"""The security event names, and the class each name belongs to."""

from __future__ import annotations

from xtr_event_dispatcher_contracts import Event, event_name_of

from xtr_security_http.event import (
    AuthenticationTokenCreatedEvent,
    CheckPassportEvent,
    CheckRefreshedUserEvent,
    InteractiveLoginEvent,
    LoginFailureEvent,
    LoginSuccessEvent,
    LogoutEvent,
    TokenDeauthenticatedEvent,
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
        InteractiveLoginEvent,
        LoginFailureEvent,
        LoginSuccessEvent,
        LogoutEvent,
        CheckRefreshedUserEvent,
        TokenDeauthenticatedEvent,
    }
    for event_class in aliases:
        assert issubclass(event_class, Event)
    # The class-keyed ones run under the qualified name the dispatcher
    # derives; the interactive login under the name it carries.
    for event_class in (
        AuthenticationTokenCreatedEvent,
        CheckPassportEvent,
        LoginFailureEvent,
        LoginSuccessEvent,
        LogoutEvent,
        CheckRefreshedUserEvent,
        TokenDeauthenticatedEvent,
    ):
        assert aliases[event_class] == event_name_of(event_class)
    assert aliases[InteractiveLoginEvent] == SecurityEvents.INTERACTIVE_LOGIN
