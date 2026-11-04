"""A message bus keeping what it is handed, or failing with the error it is given."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_messenger import Envelope, MessageBusInterface

if TYPE_CHECKING:
    from xtr_messenger.stamp import StampInterface

__all__ = ["RecordingBus"]


@final
class RecordingBus(MessageBusInterface):
    """Keeps every message and its stamps in :attr:`dispatched`, or raises :attr:`error`."""

    def __init__(self) -> None:
        self.dispatched: list[tuple[object, tuple[StampInterface, ...]]] = []
        self.error: Exception | None = None

    @override
    async def dispatch(self, message: object, *stamps: StampInterface) -> Envelope:
        if self.error is not None:
            raise self.error
        self.dispatched.append((message, stamps))
        return Envelope.wrap(message, stamps)
