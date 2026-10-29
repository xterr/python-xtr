"""The consumer of the payments provider's webhook events."""

from __future__ import annotations

from typing import final

from xtr_messenger import MessageBusInterface
from xtr_remote_event import RemoteEvent, as_remote_event_consumer

from bookshop.message.audit_event import AuditEvent

__all__ = ["PaymentWebhookConsumer"]


@final
@as_remote_event_consumer("payments")
class PaymentWebhookConsumer:
    """Hands what the payments provider sent to the audit trail, off the bus.

    The webhook endpoint answered the sender the moment the event was read — a
    sender waiting on a handler is a sender that times out and sends the webhook
    again. This runs later, where the work belongs: one consumer per type the
    routing in ``config/packages/webhook.py`` names.
    """

    __slots__ = ("_bus",)

    def __init__(self, bus: MessageBusInterface) -> None:
        """Hand events on through ``bus``."""
        self._bus = bus

    async def consume(self, event: RemoteEvent) -> None:
        """Record one payment event the provider sent."""
        _ = await self._bus.dispatch(
            AuditEvent(
                subject=f"webhook:{event.name}",
                detail=f"{event.id} carried {event.payload}",
            )
        )
