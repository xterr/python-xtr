"""The event dispatcher spy keeps its own contract: it records names and returns the event."""

from __future__ import annotations

import pytest
from xtr_event_dispatcher_contracts import Event, EventDispatcherInterface

from tests.support.event_dispatcher_spy import EventDispatcherSpy

pytestmark = pytest.mark.anyio


def test_it_is_an_event_dispatcher() -> None:
    assert isinstance(EventDispatcherSpy(), EventDispatcherInterface)


async def test_it_records_each_name_in_order_and_returns_the_event() -> None:
    dispatcher = EventDispatcherSpy()
    event = Event()

    first = await dispatcher.dispatch(event, "workflow.guard")
    second = await dispatcher.dispatch(event)

    assert first is event
    assert second is event
    assert dispatcher.dispatched_event_names == ["workflow.guard", None]
