"""Sends chat messages directly, or queues them."""

from __future__ import annotations

from typing import final

from typing_extensions import override

from ._message_sender import MessageSender
from .chatter_interface import ChatterInterface

__all__ = ["Chatter"]


@final
class Chatter(MessageSender, ChatterInterface):
    """Sends chat messages through the chat transports, or queues them on a message bus.

    ``Chatter(transport)`` sends at once; ``Chatter(transport, message_bus)``
    dispatches each message to the bus, whose handler sends it later.
    """

    __slots__ = ()

    @override
    def __str__(self) -> str:
        """Name it ``chat``."""
        return "chat"
