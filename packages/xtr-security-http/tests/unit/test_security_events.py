"""The HTTP-edge event names equal the qualified names of their event classes."""

from __future__ import annotations

from xtr_event_dispatcher_contracts import event_name_of

from xtr_security_http import security_events
from xtr_security_http.event.authentication_token_created_event import (
    AuthenticationTokenCreatedEvent,
)
from xtr_security_http.event.check_passport_event import CheckPassportEvent
from xtr_security_http.event.login_failure_event import LoginFailureEvent
from xtr_security_http.event.login_success_event import LoginSuccessEvent


def test_each_name_is_the_qualified_name_of_its_event() -> None:
    assert event_name_of(CheckPassportEvent) == security_events.CHECK_PASSPORT
    assert (
        event_name_of(
            AuthenticationTokenCreatedEvent,
        )
        == security_events.AUTHENTICATION_TOKEN_CREATED
    )
    assert event_name_of(LoginSuccessEvent) == security_events.LOGIN_SUCCESS
    assert event_name_of(LoginFailureEvent) == security_events.LOGIN_FAILURE
