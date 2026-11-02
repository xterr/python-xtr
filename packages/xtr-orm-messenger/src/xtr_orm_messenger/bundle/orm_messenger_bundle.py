"""The orm messenger bundle: the ``orm://`` transport for the container's message bus.

An application listing :class:`OrmMessengerBundle` can name ``orm://`` DSNs in
its message bus configuration: the bundle registers the transport factory with
the messenger, ahead of the factories found by DSN scheme, built on the
connections the orm bundle configures. With ``migrations_connection`` set,
the messages table also joins that connection's migrations.
"""

from __future__ import annotations

from typing import Final, final

from typing_extensions import override
from xtr_dependency_injection import (
    Bundle,
    ContainerBuilder,
    ServiceConfigurator,
    as_bundle,
    qualified_name,
    required_bundle,
)
from xtr_messenger import SerializerInterface, TransportFactoryInterface
from xtr_messenger.bundle import TRANSPORT_FACTORY_TAG, MessengerBundle
from xtr_orm import ConnectionRegistry
from xtr_orm.bundle import OrmBundle, OrmMappingsPass

from xtr_orm_messenger.transport.messages_table_driver import MessagesTableDriver
from xtr_orm_messenger.transport.orm_transport_factory import OrmTransportFactory

from .orm_messenger_config import OrmMessengerConfig

__all__ = ["CONNECTION_PARAMETER", "MAPPED_PARAMETER", "OrmMessengerBundle"]

CONNECTION_PARAMETER: Final = "orm_messenger.migrations_connection"
"""The parameter naming the connection whose migrations write the messages table."""

MAPPED_PARAMETER: Final = "orm_messenger.map_table"
"""The parameter saying whether the messages table joins those migrations."""


def orm_transport_factory(
    registry: ConnectionRegistry, serializer: SerializerInterface
) -> OrmTransportFactory:
    """Build the factory on the application's connections, with the messenger's serializer."""
    return OrmTransportFactory(registry, serializer)


@final
@required_bundle(MessengerBundle)
@required_bundle(OrmBundle)
@as_bundle("orm_messenger", config=OrmMessengerConfig)
class OrmMessengerBundle(Bundle[OrmMessengerConfig]):
    """Registers the ``orm://`` transport factory with the messenger."""

    def __init__(self) -> None:
        """Start with the mapping pass, and no table to map yet."""
        self._mappings = OrmMappingsPass(CONNECTION_PARAMETER, MAPPED_PARAMETER)

    @override
    def build(self, builder: ContainerBuilder) -> None:
        """Register the pass that maps the table; only ``build`` may."""
        builder.add_compiler_pass(self._mappings)

    @override
    def load_extension(
        self,
        config: OrmMessengerConfig,
        services: ServiceConfigurator,
        builder: ContainerBuilder,
    ) -> None:
        """Register the factory, and hand the pass the table when it is to be mapped.

        The factory is registered under
        :class:`~xtr_messenger.TransportFactoryInterface` and tagged
        :data:`~xtr_messenger.bundle.TRANSPORT_FACTORY_TAG`, which is how the
        messenger consults a factory built from services ahead of discovery.
        """
        qualifier = qualified_name(OrmTransportFactory)
        _ = services.set(orm_transport_factory, qualifier=qualifier).add_tag(TRANSPORT_FACTORY_TAG)
        services.alias(
            TransportFactoryInterface,
            OrmTransportFactory,
            alias_qualifier=qualifier,
            target_qualifier=qualifier,
        )
        mapped = config.migrations_connection is not None
        builder.set_parameter(MAPPED_PARAMETER, mapped)
        if config.migrations_connection is not None:
            builder.set_parameter(CONNECTION_PARAMETER, config.migrations_connection)
            self._mappings.set_driver(MessagesTableDriver(config.table_name))
