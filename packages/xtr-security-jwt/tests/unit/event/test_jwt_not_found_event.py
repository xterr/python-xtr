"""The not-found event is a failure event that carries and records its request."""

from __future__ import annotations

from starlette.responses import JSONResponse
from xtr_security_core.exception import AuthenticationError

from tests.support.requests import make_request
from xtr_security_jwt.event.authentication_failure_event import AuthenticationFailureEvent
from xtr_security_jwt.event.jwt_failure_event_interface import JwtFailureEventInterface
from xtr_security_jwt.event.jwt_not_found_event import JwtNotFoundEvent


def test_it_derives_from_the_failure_base_and_the_interface() -> None:
    assert AuthenticationFailureEvent in JwtNotFoundEvent.__mro__
    assert JwtFailureEventInterface in JwtNotFoundEvent.__mro__


def test_it_carries_and_records_its_request() -> None:
    event = JwtNotFoundEvent(AuthenticationError("x"), JSONResponse({}))

    assert event.get_request() is None
    request = make_request()
    event.set_request(request)
    assert event.get_request() is request
