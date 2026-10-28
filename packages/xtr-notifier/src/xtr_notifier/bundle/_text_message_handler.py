"""Sends the SMS and push messages queued on the bus through the texter's transports.

Scanned by the bundle only when the messenger bundle is active and SMS or push
transports are configured, so the bus never holds a handler it cannot build.
"""

from __future__ import annotations

from typing import Annotated, final

from xtr_dependency_injection import Target
from xtr_messenger import as_message_handler

from xtr_notifier.message import PushMessage, SentMessage, SmsMessage
from xtr_notifier.messenger import MessageHandler
from xtr_notifier.transport import Transports

__all__ = ["TextMessageHandler"]


@as_message_handler(PushMessage)
@as_message_handler(SmsMessage)
@final
class TextMessageHandler:
    """Hands each queued SMS or push message to the texter's transports."""

    __slots__ = ("_handler",)

    def __init__(self, transports: Annotated[Transports, Target("texter")]) -> None:
        """Send through ``transports``."""
        self._handler = MessageHandler(transports)

    async def __call__(self, message: SmsMessage | PushMessage) -> SentMessage:
        """Send ``message``; a provider's refusal makes the bus retry it."""
        return await self._handler(message)
