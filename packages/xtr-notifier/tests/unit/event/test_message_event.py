from __future__ import annotations

from xtr_event_dispatcher_contracts import Event

from xtr_notifier.event import MessageEvent
from xtr_notifier.message import ChatMessage


def test_it_carries_the_message_and_is_not_queued_by_default() -> None:
    message = ChatMessage("subject")

    event = MessageEvent(message)

    assert isinstance(event, Event)
    assert event.message is message
    assert event.queued is False


def test_it_says_when_the_message_was_queued() -> None:
    assert MessageEvent(ChatMessage("subject"), queued=True).queued is True
