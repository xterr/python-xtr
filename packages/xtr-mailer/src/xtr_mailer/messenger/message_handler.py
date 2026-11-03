"""Sends the emails a message bus hands back, through the transport."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, final

if TYPE_CHECKING:
    from xtr_mailer.sent_message import SentMessage
    from xtr_mailer.transport import TransportInterface

    from .send_email_message import SendEmailMessage

__all__ = ["MessageHandler"]


@final
class MessageHandler:
    """The handler of :class:`~xtr_mailer.messenger.SendEmailMessage`: sends it, then and there.

    Registered for the message on the bus — in this process, or in a worker reading the queue
    — it sends each email through the transport with the envelope it was queued with, the
    transport's listeners running on it as they would on an email sent at once.

    A transport capped by a rate limiter raises the limiter's error when no token is left; it
    goes through as it was raised, and the bus transport's retry policy decides when the email
    is tried again.
    """

    __slots__: ClassVar[tuple[str, ...]] = ("_transport",)

    def __init__(self, transport: TransportInterface) -> None:
        """Send through ``transport``."""
        self._transport: TransportInterface = transport

    async def __call__(self, message: SendEmailMessage) -> SentMessage | None:
        """Send the queued email; ``None`` when a listener rejected it.

        Raises:
            TransportError: The transport could not send it.
            LogicError: The email is raw bytes queued with no envelope.
        """
        return await self._transport.send(message.message, message.envelope)
