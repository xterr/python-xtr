from __future__ import annotations

from xtr_messenger.message_registry import name_of, type_for_name

from xtr_notifier.message import ChatMessage, PushMessage, SmsMessage
from xtr_notifier.messenger import MESSAGE_NAMES


def test_importing_it_declares_each_message_under_its_pinned_wire_name() -> None:
    for message_type in (ChatMessage, SmsMessage, PushMessage):
        assert name_of(message_type) == MESSAGE_NAMES[message_type]
        assert type_for_name(MESSAGE_NAMES[message_type]) is message_type
