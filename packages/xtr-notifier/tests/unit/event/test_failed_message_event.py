from __future__ import annotations

import pytest
from xtr_event_dispatcher_contracts import Event

from xtr_notifier.event import FailedMessageEvent
from xtr_notifier.message import ChatMessage, MessageInterface, SmsMessage


@pytest.mark.parametrize(
    ("message", "error"),
    [
        (ChatMessage("subject"), RuntimeError()),
        (SmsMessage("+3312345678", "subject"), Exception()),
    ],
)
def test_it_carries_the_message_and_the_error(message: MessageInterface, error: Exception) -> None:
    event = FailedMessageEvent(message, error)

    assert isinstance(event, Event)
    assert event.message is message
    assert event.error is error
