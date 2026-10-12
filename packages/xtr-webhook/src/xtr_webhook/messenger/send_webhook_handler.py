"""Delivers the webhook a :class:`SendWebhookMessage` asks for."""

from __future__ import annotations

from typing import final

from xtr_messenger import as_message_handler

from xtr_webhook.server.transport_interface import TransportInterface

from .send_webhook_message import SendWebhookMessage

__all__ = ["SendWebhookHandler"]


@as_message_handler(SendWebhookMessage)
@final
class SendWebhookHandler:
    """Hands the message's subscriber and event to the transport, and nothing else.

    It is handed a :class:`~xtr_webhook.server.TransportInterface`, never a
    container: delivering is the only question it has, so a handler given the
    container could reach everything else the application registered as well.

    Queueing the delivery is what keeps a slow receiver out of the request that
    caused the event. The price is that the subscriber secret travels inside the
    queued message body, so the queue storage must be trusted. The bus itself adds
    nothing to that: its logging middleware records the message type, the
    transport, the message id, the handler name and the stamps — never the body.
    """

    __slots__ = ("_transport",)

    def __init__(self, transport: TransportInterface) -> None:
        """Deliver through ``transport``."""
        self._transport = transport

    async def __call__(self, message: SendWebhookMessage) -> None:
        """Deliver ``message.event`` to ``message.subscriber``.

        Nothing is caught. A refusal is what makes the bus try the delivery
        again and, once the attempts are spent, keep the message instead of
        dropping it; swallowing it here would turn every refused webhook into
        one silently never sent.

        Raises:
            DeliveryError: When the receiver did not accept the webhook.
        """
        await self._transport.send(message.subscriber, message.event)
