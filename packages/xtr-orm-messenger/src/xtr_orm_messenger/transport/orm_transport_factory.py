"""Building ``orm://`` transports on the connections xtr-orm configures.

The DSN names a connection, not a database: ``orm://default`` is the
connection the application configured as ``default``, ``orm://`` the default
connection, whatever it is called. The database's URL, its credentials and its
pool stay where the connection is configured, so a transport never repeats
them.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, final
from urllib.parse import urlsplit

from typing_extensions import override
from xtr_messenger import PublisherClosingInterface, TransportFactoryInterface

from xtr_orm_messenger.exception import InvalidOrmDsnError

from .connection import Connection
from .orm_options import ORM_SCHEME, OrmOptions
from .orm_transport import OrmTransport

if TYPE_CHECKING:
    from collections.abc import Mapping

    from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
    from xtr_clock import ClockInterface
    from xtr_messenger import Dsn, SenderInterface, SerializerInterface, TransportConfig
    from xtr_orm import ConnectionRegistry

__all__ = ["OrmTransportFactory"]


@final
class OrmTransportFactory(TransportFactoryInterface, PublisherClosingInterface):
    """Builds ``orm://`` transports, each on the connection its DSN names.

    One transport per name, built the first time and kept: the bus sending to
    it and the worker draining it must hold the same one, as they would any
    transport holding a connection.

    Not discovered by DSN scheme like a transport needing nothing: it needs
    the application's connections, so it is either registered by its bundle or
    passed to the bus yourself::

        MessageBusFactory(config, [OrmTransportFactory(registry, serializer)])
    """

    __slots__ = ("_clock", "_made", "_registry", "_serializer")

    def __init__(
        self,
        registry: ConnectionRegistry,
        serializer: SerializerInterface,
        clock: ClockInterface | None = None,
    ) -> None:
        """Build transports on ``registry``'s connections.

        Args:
            registry: The application's connections, by name.
            serializer: What every transport encodes and decodes envelopes
                with.
            clock: What every transport reads the time from; the system clock
                when left out.
        """
        self._registry = registry
        self._serializer = serializer
        self._clock = clock
        self._made: dict[str, OrmTransport] = {}

    @override
    def supports(self, dsn: Dsn) -> bool:
        """Recognise the ``orm`` scheme."""
        return dsn.scheme == ORM_SCHEME

    @override
    def create(self, group: Mapping[str, TransportConfig]) -> Mapping[str, SenderInterface]:
        """Return the transport for each name, building it the first time.

        Building one opens nothing: the connection's engine is asked for the
        first time the transport runs a statement.

        Raises:
            InvalidOrmDsnError: When a DSN names a connection the registry
                does not hold.
            UnknownTransportOptionError: When a transport carries a setting
                this one does not accept.
            InvalidTransportOptionError: When a setting's value is not what it
                takes.
        """
        return {name: self.transport(name, config) for name, config in group.items()}

    def transport(self, name: str, config: TransportConfig) -> OrmTransport:
        """Return the transport ``name``, building it from ``config`` the first time.

        Raises:
            InvalidOrmDsnError: When the DSN names a connection the registry
                does not hold.
            UnknownTransportOptionError: When ``config`` carries a setting this
                transport does not accept.
            InvalidTransportOptionError: When a setting's value is not what it
                takes.
        """
        made = self._made.get(name)
        if made is not None:
            return made
        options = OrmOptions.from_settings(config.settings)
        connection_name = urlsplit(config.parsed.connection).netloc or self._registry.default
        if not self._registry.has(connection_name):
            raise InvalidOrmDsnError(name, connection_name, self._registry.names())
        registry = self._registry

        async def engine() -> AsyncEngine:
            return await registry.engine(connection_name)

        async def session() -> AsyncSession:
            return await registry.session(connection_name)

        made = OrmTransport(
            Connection(engine, options, session_factory=session, clock=self._clock),
            self._serializer,
            name=name,
            clock=self._clock,
        )
        self._made[name] = made
        return made

    @override
    async def close_publishers(self) -> None:
        """Release the connections the transports this factory built listen on.

        Sending holds no connection of its own — the engine's pool does, and
        the connection's owner disposes it — so this leaves only the
        connection a PostgreSQL worker listens for notifications on.
        """
        for transport in self._made.values():
            await transport.close()
