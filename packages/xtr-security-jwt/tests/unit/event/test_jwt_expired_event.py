"""The expired event is a failure event over the failure base and interface."""

from __future__ import annotations

from starlette.responses import JSONResponse
from xtr_security_core.exception import AuthenticationError

from xtr_security_jwt.event.authentication_failure_event import AuthenticationFailureEvent
from xtr_security_jwt.event.jwt_expired_event import JwtExpiredEvent
from xtr_security_jwt.event.jwt_failure_event_interface import JwtFailureEventInterface


def test_it_derives_from_the_failure_base_and_the_interface() -> None:
    assert AuthenticationFailureEvent in JwtExpiredEvent.__mro__
    assert JwtFailureEventInterface in JwtExpiredEvent.__mro__


def test_it_carries_its_exception_and_response() -> None:
    error = AuthenticationError("gone")
    response = JSONResponse({})
    event = JwtExpiredEvent(error, response)

    assert event.get_exception() is error
    assert event.get_response() is response
