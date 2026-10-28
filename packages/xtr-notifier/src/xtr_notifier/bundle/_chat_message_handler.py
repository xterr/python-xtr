"""Sends the chat messages queued on the bus through the chatter's transports.

Scanned by the bundle only when the messenger bundle is active and chat
transports are configured, so the bus never holds a handler it cannot build.
"""

from __future__ import annotations

from typing import Annotated, final

from xtr_dependency_injection import Target
from xtr_messenger import as_message_handler

from xtr_notifier.message import ChatMessage, SentMessage
from xtr_notifier.messenger import MessageHandler
from xtr_notifier.transport import Transports

__all__ = ["ChatMessageHandler"]


@as_message_handler(ChatMessage)
@final
class ChatMessageHandler:
    """Hands each queued chat message to the chatter's transports."""

    __slots__ = ("_handler",)

    def __init__(self, transports: Annotated[Transports, Target("chatter")]) -> None:
        """Send through ``transports``."""
        self._handler = MessageHandler(transports)

    async def __call__(self, message: ChatMessage) -> SentMessage:
        """Send ``message``; a provider's refusal makes the bus retry it."""
        return await self._handler(message)
