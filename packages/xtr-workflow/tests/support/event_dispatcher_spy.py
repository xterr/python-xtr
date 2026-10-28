"""An event dispatcher that records the name of every event it is handed."""

from __future__ import annotations

from typing import TypeVar, final

from typing_extensions import override
from xtr_event_dispatcher_contracts import EventDispatcherInterface

__all__ = ["EventDispatcherSpy"]

_EventT = TypeVar("_EventT")


@final
class EventDispatcherSpy(EventDispatcherInterface):
    """Records the name each event is dispatched under, in order, and runs no listener.

    What a test asserting the exact sequence of names a workflow dispatches
    needs: a real dispatcher only tells which of its listeners ran.
    """

    def __init__(self) -> None:
        self.dispatched_event_names: list[str | type | None] = []

    @override
    async def dispatch(self, event: _EventT, event_name: str | type | None = None) -> _EventT:
        self.dispatched_event_names.append(event_name)
        return event
