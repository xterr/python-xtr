"""The factory serving the private ``outbox://`` DSN scheme.

A class in a scanned module implementing ``TransportFactoryInterface`` is registered by the
messenger bundle automatically and consulted *ahead of* the factories found by entry point —
no decorator, no entry point, no factory list passed by hand. It must be buildable by the
container (here: with no arguments).

A published transport would advertise its scheme with an entry point instead::

    [project.entry-points."xtr_messenger.transport_factories"]
    outbox = "bookshop.transport.outbox_transport_factory:OutboxTransportFactory"
"""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_messenger import Dsn, TransportConfig, TransportFactoryInterface

from bookshop.transport.outbox_transport import OutboxTransport

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_messenger import SenderInterface

__all__ = ["OUTBOX_SCHEME", "OutboxTransportFactory"]

OUTBOX_SCHEME = "outbox"


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
