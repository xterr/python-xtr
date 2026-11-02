"""The emails seen so far, grouped by the transport they went to."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, final

if TYPE_CHECKING:
    from xtr_mime import RawMessage

    from .message_event import MessageEvent

__all__ = ["MessageEvents"]


@final
class MessageEvents:
    """Every email event recorded, in order, and the transports they named.

    What a test asserts on: how many emails went out, through which transport, queued or not.
    """

    __slots__: ClassVar[tuple[str, ...]] = ("_events", "_transports")

    def __init__(self) -> None:
        """Start with nothing recorded."""
        self._events: list[MessageEvent] = []
        self._transports: dict[str, None] = {}

    def add(self, event: MessageEvent) -> None:
        """Record ``event``."""
        self._events.append(event)
        self._transports[event.get_transport()] = None

    def get_transports(self) -> list[str]:
        """Return the transports named so far, each once, in the order first seen."""
        return list(self._transports)

    def get_events(self, name: str | None = None) -> list[MessageEvent]:
        """Return the events recorded, only those for the transport ``name`` when given."""
        if name is None:
            return list(self._events)
        return [event for event in self._events if event.get_transport() == name]

    def get_messages(self, name: str | None = None) -> list[RawMessage]:
        """Return the emails of :meth:`get_events`, each email once.

        An email queued on a bus that sends it in the same process is seen twice — queued, then
        sent; only the sent one is kept, as the listeners left it. An email still in the queue
        is kept as queued.
        """
        messages: list[RawMessage] = []
        sent = 0
        # Walking back, each send is matched with the queueing that came before it.
        for event in reversed(self.get_events(name)):
            if not event.is_queued():
                sent += 1
            elif sent > 0:
                sent -= 1
                continue
            messages.append(event.get_message())
        messages.reverse()
        return messages
