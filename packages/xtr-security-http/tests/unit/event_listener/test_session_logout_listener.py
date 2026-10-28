"""The logout listener that invalidates the session a request reattached."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from xtr_http_foundation import MemorySessionStorage, Session

from tests.support.messages import make_message
from xtr_security_http._security_state import security_state_of
from xtr_security_http.event.logout_event import LogoutEvent
from xtr_security_http.event_listener import SessionLogoutListener
from xtr_security_http.security_request_attributes import SecurityRequestAttributes

if TYPE_CHECKING:
    from xtr_http_message_contracts import ServerRequestInterface

pytestmark = pytest.mark.anyio


def _request_with_session() -> tuple[ServerRequestInterface, Session, MemorySessionStorage]:
    """Build a request whose security state carries the session a stateful firewall parks."""
    bag: dict[str, object] = {}
    message = make_message().with_attribute(SecurityRequestAttributes.STATE_BAG, bag)
    storage = MemorySessionStorage()
    session = Session(storage)
    security_state_of(bag).attributes[SecurityRequestAttributes.SESSION] = session
    return message, session, storage


def test_it_subscribes_to_the_logout_event_at_the_default_priority() -> None:
    assert SessionLogoutListener.get_subscribed_events() == {LogoutEvent: "on_logout"}


async def test_a_logout_invalidates_the_parked_session() -> None:
    message, session, storage = _request_with_session()
    await session.set("kept", "yes")
    await session.save()
    old_id = session.get_id()

    await SessionLogoutListener().on_logout(LogoutEvent(message, None))

    assert session.get_id() != old_id
    assert await session.get("kept") is None
    assert await storage.read(old_id) is None


async def test_a_logout_of_a_request_without_a_session_touches_nothing() -> None:
    message = make_message().with_attribute(SecurityRequestAttributes.STATE_BAG, {})

    await SessionLogoutListener().on_logout(LogoutEvent(message, None))


async def test_a_logout_of_a_request_without_a_state_bag_touches_nothing() -> None:
    await SessionLogoutListener().on_logout(LogoutEvent(make_message(), None))
