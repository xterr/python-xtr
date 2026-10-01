"""The authentication-failure event carries its exception, response and request."""

from __future__ import annotations

from starlette.responses import JSONResponse
from xtr_event_dispatcher_contracts import Event
from xtr_security_core.exception import AuthenticationError

from tests.support.requests import make_request
from xtr_security_jwt.event.authentication_failure_event import AuthenticationFailureEvent


def test_it_is_a_dispatcher_event() -> None:
    assert Event in AuthenticationFailureEvent.__mro__


def test_it_exposes_and_replaces_its_response() -> None:
    error = AuthenticationError("bad")
    first = JSONResponse({})
    second = JSONResponse({"replaced": True})
    event = AuthenticationFailureEvent(error, first)

    assert event.get_exception() is error
    assert event.get_response() is first
    event.set_response(second)
    assert event.get_response() is second


def test_it_carries_and_records_its_request() -> None:
    event = AuthenticationFailureEvent(AuthenticationError("x"), JSONResponse({}))

    assert event.get_request() is None
    request = make_request()
    event.set_request(request)
    assert event.get_request() is request
