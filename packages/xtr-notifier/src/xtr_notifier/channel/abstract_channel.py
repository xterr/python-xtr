"""The base of the channels that send through a transport or a message bus."""

from __future__ import annotations

from abc import ABC
from typing import TYPE_CHECKING

from xtr_notifier.exception import LogicError

from .channel_interface import ChannelInterface

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from xtr_messenger import MessageBusInterface

    from xtr_notifier.message import MessageInterface
    from xtr_notifier.transport import TransportInterface

__all__ = ["AbstractChannel"]


class AbstractChannel(ChannelInterface, ABC):
    """Hands each message to a transport — or, given a message bus, to the bus.

    With a bus the message is queued and a handler sends it later through the
    transport configured there; the bus wins when both are given. A subclass
    builds the message and calls :meth:`_deliver`.
    """

    def __init__(
        self,
        transport: TransportInterface | None = None,
        message_bus: MessageBusInterface | None = None,
    ) -> None:
        """Deliver through ``transport``, or queue on ``message_bus``.

        Args:
            transport: What sends the messages when there is no bus.
            message_bus: Where messages are queued instead of sent now.

        Raises:
            LogicError: If both are ``None``: the channel would have nowhere to
                send.
        """
        deliver: Callable[[MessageInterface], Awaitable[object]]
        if message_bus is not None:
            deliver = message_bus.dispatch
        elif transport is not None:
            deliver = transport.send
        else:
            raise LogicError(
                f'"{type(self).__name__}" needs a Transport or a Bus but both cannot be "None".'
            )
        self._deliver_to: Callable[[MessageInterface], Awaitable[object]] = deliver

    async def _deliver(self, message: MessageInterface) -> None:
        """Send ``message`` through the transport, or queue it on the bus."""
        _ = await self._deliver_to(message)
