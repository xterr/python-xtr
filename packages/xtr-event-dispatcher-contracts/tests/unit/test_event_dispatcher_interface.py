from __future__ import annotations

from xtr_event_dispatcher_contracts import EventDispatcherInterface


class _SilentDispatcher:
    async def dispatch[EventT](self, event: EventT, event_name: str | type | None = None) -> EventT:
        del event_name
        return event


def test_an_object_that_dispatches_is_a_dispatcher() -> None:
    dispatcher: EventDispatcherInterface = _SilentDispatcher()

    assert isinstance(dispatcher, EventDispatcherInterface)


def test_a_plain_object_is_not_a_dispatcher() -> None:
    assert not isinstance(object(), EventDispatcherInterface)
