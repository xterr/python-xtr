"""The messages seen so far, grouped by the transport they went to."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

if TYPE_CHECKING:
    from xtr_notifier.message import MessageInterface

    from .message_event import MessageEvent

__all__ = ["NotificationEvents"]


@final
class NotificationEvents:
    """Every message event recorded, in order, and the transports they named.

    What a test asserts on: how many messages went out, through which
    transport, queued or not. A message naming no transport is filed under
    ``""``.
    """

    __slots__ = ("_events", "_transports")

    def __init__(self) -> None:
        """Start with nothing recorded."""
        self._events: list[MessageEvent] = []
        self._transports: dict[str, None] = {}

    def add(self, event: MessageEvent) -> None:
        """Record ``event``."""
        self._events.append(event)
        self._transports[event.message.transport or ""] = None

    @property
    def transports(self) -> list[str]:
        """The transports named so far, each once, in the order first seen."""
        return list(self._transports)

    def get_events(self, name: str | None = None) -> list[MessageEvent]:
        """Return the events recorded, only those for the transport ``name`` when given."""
        if name is None:
            return list(self._events)
        return [event for event in self._events if (event.message.transport or "") == name]

    def get_messages(self, name: str | None = None) -> list[MessageInterface]:
        """Return the messages of :meth:`get_events`."""
        return [event.message for event in self.get_events(name)]
