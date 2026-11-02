"""Stand-ins for the message bus, for testing the transport alone."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_messenger import Envelope, MessageBusInterface

if TYPE_CHECKING:
    from xtr_messenger import StampInterface


@final
class RecordingBus(MessageBusInterface):
    """A bus that records what it is given, optionally failing every dispatch."""

    def __init__(self, failure: Exception | None = None) -> None:
        self.dispatched: list[Envelope] = []
        self._failure = failure

    @override
    async def dispatch(self, message: object, *stamps: StampInterface) -> Envelope:
        envelope = Envelope.wrap(message, stamps)
        self.dispatched.append(envelope)
        if self._failure is not None:
            raise self._failure
        return envelope
