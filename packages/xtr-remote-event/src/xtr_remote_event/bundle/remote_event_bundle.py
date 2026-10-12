"""The xtr-remote-event bundle: declared consumers, reachable by the name of their source.

An application listing :class:`RemoteEventBundle` — which brings
``MessengerBundle`` with it — gets every class declared with
``@as_remote_event_consumer`` built by the container with its dependencies,
and a ``ConsumeRemoteEventMessage`` dispatched on the bus handed to whichever
of them answers for its source. The handler is registered with it, so a wired
application never meets ``NoHandlerForMessageError`` for that message.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, final

from typing_extensions import override
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
from xtr_remote_event.exception import LogicError

from ._declared_consumers import DeclaredConsumers
from .remote_event_config import RemoteEventConfig

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

__all__ = ["RemoteEventBundle"]

_CONSUMER_LOCATOR: Final = "remote_event_consumers"

_NO_CONTAINER: Final = "the remote event bundle has no container; it is used before it booted"

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
        event arrived under.
        """
        declared = self._declared

        def register(obj: object, name: str, services: ServiceConfigurator) -> None:
            if isinstance(obj, type) and declared.add(name, obj):
                _ = services.set(obj)

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
        """Register the consumer locator, and the handler that looks consumers up in it."""
        del config, builder
        _ = services.set(named_factory(_consumer_locator(self, self._declared), _CONSUMER_LOCATOR))
        services.load(_HANDLER_MODULE)


def _consumer_locator(
    bundle: RemoteEventBundle, declared: DeclaredConsumers
) -> Callable[[], Coroutine[None, None, ConsumerLocator]]:
    """Return a factory serving the container's consumers through a :class:`ServiceLocator`.

    The locator is what the handler is given, so the handler never holds the
    container, and a consumer is built — with its dependencies — only when an
    event for its source first arrives.
    """

    async def build() -> ConsumerLocator:
        container = bundle.container
        if container is None:
            raise LogicError(_NO_CONTAINER)
        return ConsumerLocator(
            ServiceLocator[ConsumerInterface](
                container, {name: (cls, None) for name, cls in declared.items()}
            )
        )

    return build
