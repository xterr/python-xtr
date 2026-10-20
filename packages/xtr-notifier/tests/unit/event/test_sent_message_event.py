from __future__ import annotations

import pytest
from xtr_event_dispatcher_contracts import Event

from xtr_notifier.event import SentMessageEvent
from xtr_notifier.message import ChatMessage, SentMessage, SmsMessage


@pytest.mark.parametrize(
    "sent",
    [
        SentMessage(ChatMessage("subject"), "null_transport"),
        SentMessage(SmsMessage("+3312345678", "subject"), "null_transport"),
    ],
)
def test_it_carries_the_sent_message(sent: SentMessage) -> None:
    event = SentMessageEvent(sent)

    assert isinstance(event, Event)
    assert event.message is sent
