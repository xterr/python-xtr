"""The event-name constants stand for the qualified names of their events."""

from __future__ import annotations

from xtr_event_dispatcher_contracts import event_name_of

from xtr_security_jwt.event.authentication_failure_event import AuthenticationFailureEvent
from xtr_security_jwt.event.authentication_success_event import AuthenticationSuccessEvent
from xtr_security_jwt.event.jwt_authenticated_event import JwtAuthenticatedEvent
from xtr_security_jwt.event.jwt_created_event import JwtCreatedEvent
from xtr_security_jwt.event.jwt_decoded_event import JwtDecodedEvent
from xtr_security_jwt.event.jwt_encoded_event import JwtEncodedEvent
from xtr_security_jwt.event.jwt_expired_event import JwtExpiredEvent
from xtr_security_jwt.event.jwt_invalid_event import JwtInvalidEvent
from xtr_security_jwt.event.jwt_not_found_event import JwtNotFoundEvent
from xtr_security_jwt.events import Events


def test_each_constant_is_the_qualified_name_of_its_event() -> None:
    assert event_name_of(JwtCreatedEvent) == Events.JWT_CREATED
    assert event_name_of(JwtEncodedEvent) == Events.JWT_ENCODED
    assert event_name_of(JwtDecodedEvent) == Events.JWT_DECODED
    assert event_name_of(JwtAuthenticatedEvent) == Events.JWT_AUTHENTICATED
    assert event_name_of(JwtInvalidEvent) == Events.JWT_INVALID
    assert event_name_of(JwtNotFoundEvent) == Events.JWT_NOT_FOUND
    assert event_name_of(JwtExpiredEvent) == Events.JWT_EXPIRED
    assert event_name_of(AuthenticationSuccessEvent) == Events.AUTHENTICATION_SUCCESS
    assert event_name_of(AuthenticationFailureEvent) == Events.AUTHENTICATION_FAILURE


def test_the_names_are_all_distinct() -> None:
    names = {
        Events.JWT_CREATED,
        Events.JWT_ENCODED,
        Events.JWT_DECODED,
        Events.JWT_AUTHENTICATED,
        Events.JWT_INVALID,
        Events.JWT_NOT_FOUND,
        Events.JWT_EXPIRED,
        Events.AUTHENTICATION_SUCCESS,
        Events.AUTHENTICATION_FAILURE,
    }

    assert len(names) == 9
