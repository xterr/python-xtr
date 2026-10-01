"""A dispatcher that records what it was asked to dispatch."""

from __future__ import annotations

from typing import TypeVar, final

_EventT = TypeVar("_EventT")


@final
class RecordingDispatcher:
    """Keeps every event it dispatches, so a test can read them back."""

    def __init__(self) -> None:
        self.events: list[object] = []

    async def dispatch(self, event: _EventT, event_name: str | type | None = None) -> _EventT:
        del event_name
        self.events.append(event)
        return event
