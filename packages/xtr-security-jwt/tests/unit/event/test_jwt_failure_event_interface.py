"""The failure events satisfy the runtime-checkable failure interface."""

from __future__ import annotations

from starlette.responses import JSONResponse
from xtr_security_core.exception import AuthenticationError

from xtr_security_jwt.event.jwt_expired_event import JwtExpiredEvent
from xtr_security_jwt.event.jwt_failure_event_interface import JwtFailureEventInterface
from xtr_security_jwt.event.jwt_invalid_event import JwtInvalidEvent
from xtr_security_jwt.event.jwt_not_found_event import JwtNotFoundEvent


def test_every_failure_event_is_an_instance_of_the_interface() -> None:
    response = JSONResponse({})
    error = AuthenticationError("bad")
    for event in (
        JwtInvalidEvent(error, response),
        JwtExpiredEvent(error, response),
        JwtNotFoundEvent(error, response),
    ):
        assert isinstance(event, JwtFailureEventInterface)
