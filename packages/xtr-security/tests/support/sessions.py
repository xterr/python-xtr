"""Building a request whose state carries a parked session, for the tests.

The context listener parks the session it reattaches on the request's state
bag; the tests that read or write through the park build the same shape by
hand — the bag, the state in it, the session on the state.
"""

from __future__ import annotations

from xtr_http_foundation import MemorySessionStorage, Session
from xtr_http_message import ServerRequest
from xtr_security_http._security_state import security_state_of
from xtr_security_http.security_request_attributes import SecurityRequestAttributes

from tests.support.messages import make_message

__all__ = ["request_parking_a_session"]


def request_parking_a_session() -> tuple[ServerRequest, Session]:
    """Return a request whose state bag carries a parked session, and the session."""
    request = make_message()
    bag: dict[str, object] = {}
    session = Session.from_request(request, MemorySessionStorage())
    security_state_of(bag).attributes[SecurityRequestAttributes.SESSION] = session
    return request.with_attribute(SecurityRequestAttributes.STATE_BAG, bag), session
