"""Sends the messages a chatter, a texter or a channel queued on the bus."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

if TYPE_CHECKING:
    from xtr_notifier.message import ChatMessage, PushMessage, SentMessage, SmsMessage
    from xtr_notifier.transport import TransportInterface

__all__ = ["MessageHandler"]


@final
class MessageHandler:
    """Hands each queued message to the transport, which sends it.

    Register one per kind of transport — over the chat transports for
    :class:`~xtr_notifier.message.ChatMessage`, over the texter's for
    :class:`~xtr_notifier.message.SmsMessage` and
    :class:`~xtr_notifier.message.PushMessage` — so the message is sent by the
    same transports it would have been sent by without the bus. Nothing is
    caught: a provider's refusal is what makes the bus retry the message.
    """

    __slots__ = ("_transport",)

    def __init__(self, transport: TransportInterface) -> None:
        """Send through ``transport``."""
        self._transport = transport

    async def __call__(self, message: ChatMessage | SmsMessage | PushMessage) -> SentMessage:
        """Send ``message`` and report it.

        Raises:
            TransportError: When the provider cannot be reached or refuses it.
        """
        return await self._transport.send(message)
