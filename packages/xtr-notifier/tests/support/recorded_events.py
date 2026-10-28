"""A real event dispatcher, with every notifier event it dispatches recorded."""

from __future__ import annotations

from xtr_event_dispatcher import EventDispatcher

from xtr_notifier.event import FailedMessageEvent, MessageEvent, SentMessageEvent

__all__ = ["recording_dispatcher"]


def recording_dispatcher() -> tuple[EventDispatcher, list[object]]:
    """Return a dispatcher and the list each notifier event it dispatches is appended to."""
    dispatcher = EventDispatcher()
    recorded: list[object] = []
    for event in (MessageEvent, SentMessageEvent, FailedMessageEvent):
        dispatcher.add_listener(event, recorded.append)
    return dispatcher, recorded
