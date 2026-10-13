"""The authentication event names match the keys the events are dispatched under."""

from __future__ import annotations

from xtr_event_dispatcher_contracts import event_name_of

from xtr_security_core.authentication_events import AuthenticationEvents
from xtr_security_core.event import AuthenticationSuccessEvent


def test_authentication_success_names_the_success_event() -> None:
    assert event_name_of(AuthenticationSuccessEvent) == AuthenticationEvents.AUTHENTICATION_SUCCESS
