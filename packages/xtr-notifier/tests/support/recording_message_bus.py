"""A bus that keeps what was dispatched instead of sending it anywhere."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_messenger import Envelope, MessageBusInterface

if TYPE_CHECKING:
    from xtr_messenger.stamp import StampInterface

__all__ = ["RecordingMessageBus"]


@final
class RecordingMessageBus(MessageBusInterface):
    """Records every dispatched message in ``messages``, in order."""

    def __init__(self) -> None:
        self.messages: list[object] = []

    @override
    async def dispatch(self, message: object, *stamps: StampInterface) -> Envelope:
        self.messages.append(message)
        return Envelope(message, stamps)
