"""A transport of the application's own, serving the private ``outbox://`` DSN scheme.

A class in a scanned module implementing ``TransportFactoryInterface`` is registered by the
messenger bundle automatically and consulted *ahead of* the factories found by entry point —
no decorator, no entry point, no factory list passed by hand. It must be buildable by the
container (here: with no arguments).

A published transport would advertise its scheme with an entry point instead::

    [project.entry-points."xtr_messenger.transport_factories"]
    outbox = "bookshop.messaging.outbox_transport:OutboxTransportFactory"
"""

from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_dependency_injection import exclude
from xtr_messenger import (
    Dsn,
    EncodedEnvelope,
    JsonSerializer,
    ReceivedStamp,
    TransportConfig,
    TransportFactoryInterface,
    TransportInterface,
    TransportMessageIdStamp,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Mapping

    from xtr_messenger import Envelope, SenderInterface

__all__ = ["OutboxTransport", "OutboxTransportFactory", "UnusedTransportFactory"]

OUTBOX_SCHEME = "outbox"


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


@final
class OutboxTransportFactory(TransportFactoryInterface):
    """Builds one :class:`OutboxTransport` per transport name, and reuses it.

    The bus and every worker must share the transport a name stands for, so the factory —
    a singleton in the container — keeps what it built.
    """

    __slots__ = ("_made",)

    def __init__(self) -> None:
        """Start with nothing built."""
        self._made: dict[str, OutboxTransport] = {}

    @override
    def supports(self, dsn: Dsn) -> bool:
        return dsn.scheme == OUTBOX_SCHEME

    @override
    def create(self, group: Mapping[str, TransportConfig]) -> Mapping[str, SenderInterface]:
        return {name: self.transport(name) for name in group}

    def transport(self, name: str) -> OutboxTransport:
        """The transport ``name`` stands for, built the first time."""
        made = self._made.get(name)
        if made is None:
            made = OutboxTransport(name)
            self._made[name] = made
        return made


@final
@exclude
class UnusedTransportFactory(TransportFactoryInterface):
    """Kept out of the container with ``@exclude``.

    The messenger bundle registers *every* concrete ``TransportFactoryInterface`` its scan
    finds. ``@exclude`` is how a scanned module keeps one that is not meant for the kernel —
    a stub for container-less scripts, say — out of every scan.
    """

    @override
    def supports(self, dsn: Dsn) -> bool:
        return False

    @override
    def create(self, group: Mapping[str, TransportConfig]) -> Mapping[str, SenderInterface]:
        return {}
