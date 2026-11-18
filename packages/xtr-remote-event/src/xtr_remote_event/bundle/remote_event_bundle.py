"""The xtr-remote-event bundle: declared consumers, reachable by the name of their source.

An application listing :class:`RemoteEventBundle` — which brings
``MessengerBundle`` with it — gets every class declared with
``@as_remote_event_consumer`` built by the container with its dependencies,
and a ``ConsumeRemoteEventMessage`` dispatched on the bus handed to whichever
of them answers for its source. The handler is registered with it, so a wired
application never meets ``NoHandlerForMessageError`` for that message.

Consumers are built in the unit of work of the message they consume, so a
consumer may be scoped and share the message's session with everything else
handling it.
"""

from __future__ import annotations

from typing import Final, final, override

from xtr_dependency_injection import (
    Bundle,
    ContainerBuilder,
    ServiceConfigurator,
    ServiceLocator,
    as_bundle,
    named_factory,
    required_bundle,
)
from xtr_messenger.bundle import MessengerBundle

from xtr_remote_event.consumer.consumer_interface import ConsumerInterface
from xtr_remote_event.consumer.consumer_locator import ConsumerLocator
from xtr_remote_event.decorator import remote_event_consumers_declared_on
from xtr_remote_event.messenger.consume_remote_event_handler import ConsumeRemoteEventHandler

from ._declared_consumers import DeclaredConsumers
from .remote_event_config import RemoteEventConfig

__all__ = ["RemoteEventBundle"]

_CONSUMER_LOCATOR: Final = "remote_event_consumers"

_HANDLER_MODULE: Final = "xtr_remote_event.messenger.consume_remote_event_handler"


@final
@required_bundle(MessengerBundle)
@as_bundle("remote_event", config=RemoteEventConfig)
class RemoteEventBundle(Bundle[RemoteEventConfig]):
    """Wires declared consumers to the container, and the handler to the message bus."""

    def __init__(self) -> None:
        """Start with nothing declared."""
        self._declared = DeclaredConsumers()

    @override
    def build(self, builder: ContainerBuilder) -> None:
        """Collect every declared consumer, and register each class as one service.

        Unqualified and once, however many sources a class declared: a
        consumer answering for two of them is one instance answering for both,
        so what it remembers between events does not depend on which name the
        event arrived under. Each name is an alias of it under
        :class:`ConsumerInterface`, which is how the container's locator of
        consumers knows it by that name.
        """
        declared = self._declared

        def register(obj: object, name: str, services: ServiceConfigurator) -> None:
            if not isinstance(obj, type):
                return
            if declared.add(name, obj):
                _ = services.set(obj)
            services.alias(ConsumerInterface, obj, alias_qualifier=name)

        builder.register_attribute_for_autoconfiguration(
            remote_event_consumers_declared_on, register
        )

    @override
    def load_extension(
        self,
        config: RemoteEventConfig,
        services: ServiceConfigurator,
        builder: ContainerBuilder,
    ) -> None:
        """Register the consumer locator, and the handler that looks consumers up in it.

        Both are scoped: the handler is built in the unit of the message it
        handles, and its locator builds a consumer in that same unit.
        """
        del config, builder
        _ = services.set(named_factory(_consumer_locator, _CONSUMER_LOCATOR), lifetime="scoped")
        _ = services.set(ConsumeRemoteEventHandler, lifetime="scoped")
        services.load(_HANDLER_MODULE)


def _consumer_locator(consumers: ServiceLocator[ConsumerInterface]) -> ConsumerLocator:
    """Serve the consumers the container knows by source name.

    The locator is what the handler is given, so the handler never holds the
    container, and a consumer is built — with its dependencies, in the unit
    the locator was built in — only when an event for its source arrives.
    """
    return ConsumerLocator(consumers)
