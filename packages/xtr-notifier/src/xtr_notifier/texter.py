"""Sends text and push messages directly, or queues them."""

from __future__ import annotations

from typing import final

from typing_extensions import override

from ._message_sender import MessageSender
from .texter_interface import TexterInterface

__all__ = ["Texter"]


@final
class Texter(MessageSender, TexterInterface):
    """Sends SMS and push messages through the texter transports, or queues them on a bus.

    ``Texter(transport)`` sends at once; ``Texter(transport, message_bus)``
    dispatches each message to the bus, whose handler sends it later.
    """

    __slots__ = ()

    @override
    def __str__(self) -> str:
        """Name it ``texter``."""
        return "texter"
