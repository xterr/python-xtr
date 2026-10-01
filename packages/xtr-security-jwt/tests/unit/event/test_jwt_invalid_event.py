"""The invalid event is a failure event exposing and replacing its response."""

from __future__ import annotations

from starlette.responses import JSONResponse
from xtr_security_core.exception import AuthenticationError

from xtr_security_jwt.event.authentication_failure_event import AuthenticationFailureEvent
from xtr_security_jwt.event.jwt_failure_event_interface import JwtFailureEventInterface
from xtr_security_jwt.event.jwt_invalid_event import JwtInvalidEvent


def test_it_derives_from_the_failure_base_and_the_interface() -> None:
    assert AuthenticationFailureEvent in JwtInvalidEvent.__mro__
    assert JwtFailureEventInterface in JwtInvalidEvent.__mro__


def test_it_exposes_and_replaces_its_response() -> None:
    error = AuthenticationError("bad")
    first = JSONResponse({})
    second = JSONResponse({"replaced": True})
    event = JwtInvalidEvent(error, first)

    assert event.get_exception() is error
    assert event.get_response() is first
    event.set_response(second)
    assert event.get_response() is second
