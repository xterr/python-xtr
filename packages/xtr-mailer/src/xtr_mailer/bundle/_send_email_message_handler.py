"""Sends the emails queued on the bus through the mailer's transports.

Scanned by the bundle only when the messenger bundle is active, so the bus never holds a
handler it cannot build — in the process queuing email, and in a worker sending it. The bundle
has declared the queued email to the bus by then.
"""

from __future__ import annotations

from typing import final

from xtr_messenger import as_message_handler

from xtr_mailer.messenger import MessageHandler, SendEmailMessage
from xtr_mailer.sent_message import SentMessage
from xtr_mailer.transport.transport_interface import TransportInterface

__all__ = ["SendEmailMessageHandler"]


@as_message_handler(SendEmailMessage)
@final
class SendEmailMessageHandler:
    """Hands each queued email to the mailer's transports."""

    __slots__ = ("_handler",)

    def __init__(self, transport: TransportInterface) -> None:
        """Send through ``transport``."""
        self._handler = MessageHandler(transport)

    async def __call__(self, message: SendEmailMessage) -> SentMessage | None:
        """Send ``message``; a transport's refusal makes the bus retry it."""
        return await self._handler(message)
