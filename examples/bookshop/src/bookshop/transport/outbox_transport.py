"""The ``outbox://`` transport itself: messages kept encoded until a worker collects them."""

from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_messenger import (
    EncodedEnvelope,
    JsonSerializer,
    ReceivedStamp,
    TransportInterface,
    TransportMessageIdStamp,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from xtr_messenger import Envelope

__all__ = ["OutboxTransport"]


@final
class OutboxTransport(TransportInterface):
    """Keeps messages as they would travel — encoded — until a worker collects them.

    Implements the whole ``TransportInterface``: ``send`` for the bus, ``get`` / ``ack`` /
    ``reject`` for the library's ``Worker``. ``get`` stops once the outbox is empty, so a
    worker returns once it has drained it.
    """

    __slots__ = ("_counter", "_pending", "_serializer", "delivered", "failed", "name")

    def __init__(self, name: str) -> None:
        """Start empty; encode with the JSON serializer every transport uses by default."""
        self.name = name
        self._serializer = JsonSerializer()
        self._pending: deque[tuple[str, EncodedEnvelope]] = deque()
        self._counter = 0
        self.delivered: list[str] = []
        self.failed: list[str] = []

    @property
    def pending(self) -> int:
        """How many messages wait for a worker."""
        return len(self._pending)

    @override
    async def send(self, envelope: Envelope) -> Envelope:
        self._counter += 1
        message_id = f"{self.name}-{self._counter}"
        self._pending.append((message_id, self._serializer.encode(envelope)))
        return envelope.with_stamps(TransportMessageIdStamp(message_id))

    @override
    async def get(self) -> AsyncIterator[Envelope]:
        while self._pending:
            message_id, encoded = self._pending.popleft()
            envelope = self._serializer.decode(encoded)
            yield envelope.with_stamps(
                ReceivedStamp(self.name), TransportMessageIdStamp(message_id)
            )

    @override
    async def ack(self, envelope: Envelope) -> None:
        stamp = envelope.last(TransportMessageIdStamp)
        self.delivered.append(stamp.message_id if stamp else "?")

    @override
    async def reject(self, envelope: Envelope) -> None:
        stamp = envelope.last(TransportMessageIdStamp)
        self.failed.append(stamp.message_id if stamp else "?")
