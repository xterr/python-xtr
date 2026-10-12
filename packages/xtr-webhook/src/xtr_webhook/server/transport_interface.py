"""What delivers a built webhook to one subscriber."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from xtr_remote_event import RemoteEvent

    from xtr_webhook.subscriber import Subscriber

__all__ = ["TransportInterface"]


@runtime_checkable
class TransportInterface(Protocol):
    """Sends one event to one subscriber, or raises.

    Its own contract rather than the transport class itself, because the send
    handler and the bundle wire against *something that delivers*, and a test —
    or an application with an unusual receiver — swaps in its own without
    touching how deliveries are queued.

    Returning nothing is the point: a delivery either happened or raised a
    :class:`DeliveryError <xtr_webhook.exception.DeliveryError>`, and the error
    is what makes the message bus retry it.
    """

    async def send(self, subscriber: Subscriber, event: RemoteEvent) -> None:
        """Deliver ``event`` to ``subscriber``.

        Args:
            subscriber: Where the webhook goes, and the secret it is signed
                with.
            event: What to deliver.

        Raises:
            DeliveryError: When the receiver did not accept it.
        """
        ...
