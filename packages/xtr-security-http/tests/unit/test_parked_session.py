"""The reader of the session a stateful firewall parks on a request's security state."""

from __future__ import annotations

from xtr_http_foundation import MemorySessionStorage, Session

import xtr_security_http
from tests.support.messages import make_message
from xtr_security_http import parked_session_of
from xtr_security_http._security_state import security_state_of
from xtr_security_http.security_request_attributes import SecurityRequestAttributes


def test_parked_session_of_is_public() -> None:
    assert "parked_session_of" in xtr_security_http.__all__
    assert parked_session_of.__module__ == "xtr_security_http.parked_session"


def test_the_session_parked_on_the_state_bag_is_returned() -> None:
    bag: dict[str, object] = {}
    session = Session(MemorySessionStorage())
    security_state_of(bag).attributes[SecurityRequestAttributes.SESSION] = session
    request = make_message().with_attribute(SecurityRequestAttributes.STATE_BAG, bag)

    parked = parked_session_of(request)

    assert parked is session


def test_a_request_without_a_state_bag_has_no_parked_session() -> None:
    request = make_message()

    parked = parked_session_of(request)

    assert parked is None
