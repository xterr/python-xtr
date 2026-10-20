"""What the chatter and the texter share: send now, or queue on a bus."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from xtr_notifier.event import MessageEvent

if TYPE_CHECKING:
    from xtr_event_dispatcher_contracts import EventDispatcherInterface
    from xtr_messenger import MessageBusInterface

    from xtr_notifier.message import MessageInterface, SentMessage
    from xtr_notifier.transport import TransportInterface

__all__ = ["MessageSender"]


class MessageSender:
    """Sends through a transport, or — given a message bus — queues on it instead.

    With a bus the message is dispatched there and a handler sends it through
    the same transport later, possibly in another process; ``send`` then
    returns ``None``, since nothing was sent yet. The queued message is
    announced as a :class:`~xtr_notifier.event.MessageEvent` with ``queued``
    set, so a listener sees it once whichever way it leaves.

    The bus is only ever called, so the messenger package is needed only by an
    application that hands one over.
    """

    __slots__: ClassVar[tuple[str, ...]] = ("_event_dispatcher", "_message_bus", "_transport")

    def __init__(
        self,
        transport: TransportInterface,
        message_bus: MessageBusInterface | None = None,
        event_dispatcher: EventDispatcherInterface | None = None,
    ) -> None:
        """Send through ``transport``, or queue on ``message_bus`` when given one.

        Args:
            transport: What sends the messages, now or when the bus hands them back.
            message_bus: Where messages are queued instead of sent now; ``None``
                sends every message at once.
            event_dispatcher: Where a queued message is announced; ``None``
                announces nothing.
        """
        self._transport: TransportInterface = transport
        self._message_bus: MessageBusInterface | None = message_bus
        self._event_dispatcher: EventDispatcherInterface | None = event_dispatcher

    def supports(self, message: MessageInterface) -> bool:
        """Tell whether the transport sends ``message``."""
        return self._transport.supports(message)

    async def send(self, message: MessageInterface) -> SentMessage | None:
        """Send ``message`` and report it, or queue it on the bus and return ``None``."""
        if self._message_bus is None:
            return await self._transport.send(message)
        if self._event_dispatcher is not None:
            _ = await self._event_dispatcher.dispatch(MessageEvent(message, queued=True))
        _ = await self._message_bus.dispatch(message)
        return None
