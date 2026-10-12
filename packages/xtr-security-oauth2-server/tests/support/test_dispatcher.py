"""The recording dispatcher answers the event and really runs its listeners."""

from __future__ import annotations

import pytest
from xtr_event_dispatcher_contracts import EventDispatcherInterface

from tests.support.dispatcher import RecordingEventDispatcher

pytestmark = pytest.mark.anyio


def test_it_satisfies_the_dispatcher_contract() -> None:
    assert isinstance(RecordingEventDispatcher(), EventDispatcherInterface)


async def test_it_answers_the_event_it_was_handed() -> None:
    dispatcher = RecordingEventDispatcher()
    event = object()

    assert await dispatcher.dispatch(event, "some.event") is event


async def test_it_records_the_name_dispatched_under() -> None:
    dispatcher = RecordingEventDispatcher()

    _ = await dispatcher.dispatch(object(), "some.event")

    assert dispatcher.names() == ("some.event",)


async def test_it_runs_the_listeners_of_that_name_in_order() -> None:
    dispatcher = RecordingEventDispatcher()
    seen: list[str] = []
    dispatcher.listen("some.event", lambda _event: seen.append("first"))
    dispatcher.listen("some.event", lambda _event: seen.append("second"))

    _ = await dispatcher.dispatch(object(), "some.event")

    assert seen == ["first", "second"]


async def test_it_runs_no_listener_of_another_name() -> None:
    dispatcher = RecordingEventDispatcher()
    seen: list[str] = []
    dispatcher.listen("other.event", lambda _event: seen.append("ran"))

    _ = await dispatcher.dispatch(object(), "some.event")

    assert seen == []


async def test_only_refuses_when_more_than_one_was_dispatched() -> None:
    dispatcher = RecordingEventDispatcher()
    _ = await dispatcher.dispatch(object(), "some.event")
    _ = await dispatcher.dispatch(object(), "some.event")

    with pytest.raises(AssertionError, match="exactly one dispatch"):
        _ = dispatcher.only()
