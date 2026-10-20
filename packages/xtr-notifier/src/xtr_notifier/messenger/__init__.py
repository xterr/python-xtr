"""Sending queued messages: their wire names, and the handler a message bus calls with them.

A chatter, a texter or a channel given a message bus dispatches each message
there instead of sending it; register :class:`MessageHandler` for the message
types so a worker — or the bus itself, in-process — sends them.

Importing this package declares the chat, SMS and push messages to the bus
under stable wire names, which is what lets a worker decode them off an
asynchronous transport. Needs the ``messenger`` extra.
"""

from __future__ import annotations

from typing import Final

from xtr_messenger import register_message

from xtr_notifier.message import ChatMessage, PushMessage, SmsMessage

from .message_handler import MessageHandler

__all__ = ["MESSAGE_NAMES", "MessageHandler"]

#: The wire name of each message, pinned so a queued message still decodes after
#: a module is renamed.
MESSAGE_NAMES: Final = {
    ChatMessage: "xtr_notifier.chat_message.v1",
    SmsMessage: "xtr_notifier.sms_message.v1",
    PushMessage: "xtr_notifier.push_message.v1",
}

for _message_type, _name in MESSAGE_NAMES.items():
    register_message(_message_type, _name)
