from __future__ import annotations

from typing import TypeVar

from xtr_event_dispatcher_contracts import EventDispatcherInterface

_EventT = TypeVar("_EventT")


class _SilentDispatcher:
    async def dispatch(self, event: _EventT, event_name: str | type | None = None) -> _EventT:
        del event_name
        return event


def test_an_object_that_dispatches_is_a_dispatcher() -> None:
    dispatcher: EventDispatcherInterface = _SilentDispatcher()

    assert isinstance(dispatcher, EventDispatcherInterface)


def test_a_plain_object_is_not_a_dispatcher() -> None:
    assert not isinstance(object(), EventDispatcherInterface)
