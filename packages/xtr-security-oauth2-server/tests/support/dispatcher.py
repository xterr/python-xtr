"""A dispatcher that records what it was handed, and runs listeners for real.

The bundle layer announces six things and reads the answers back off the
events, so a test needs two assurances: that the right event was dispatched
under the right name — a mismatch between the name a listener registers and
the name the code dispatches under reaches nobody and breaks nothing loudly —
and that whatever a listener changed is what the caller then uses.

This fake gives both. It is not a mock: the listeners it holds really run, in
registration order, and the event they changed is the one handed back.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar, final

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

__all__ = ["Dispatched", "RecordingEventDispatcher"]

_EventT = TypeVar("_EventT")


@final
class Dispatched:
    """One dispatch: the event, and the name it went out under."""

    __slots__ = ("event", "name")

    def __init__(self, event: object, name: object) -> None:
        self.event = event
        self.name = name


@final
class RecordingEventDispatcher:
    """Records every dispatch and runs the listeners registered by name."""

    __slots__ = ("_listeners", "dispatched")

    def __init__(self) -> None:
        self.dispatched: list[Dispatched] = []
        self._listeners: dict[str, list[Callable[[object], None]]] = {}

    def listen(self, name: str, listener: Callable[[object], None]) -> None:
        """Run ``listener`` for every event dispatched under ``name``."""
        self._listeners.setdefault(name, []).append(listener)

    async def dispatch(self, event: _EventT, event_name: str | type | None = None) -> _EventT:
        """Record the dispatch, run the listeners of ``event_name``, answer the event."""
        self.dispatched.append(Dispatched(event, event_name))
        if isinstance(event_name, str):
            for listener in self._listeners.get(event_name, ()):
                listener(event)

        return event

    def names(self) -> Sequence[object]:
        """Return the names dispatched under, in order."""
        return tuple(record.name for record in self.dispatched)

    def only(self) -> Dispatched:
        """Return the single dispatch made, failing when there was not exactly one."""
        if len(self.dispatched) != 1:
            message = f"Expected exactly one dispatch, got {len(self.dispatched)}."
            raise AssertionError(message)

        return self.dispatched[0]
