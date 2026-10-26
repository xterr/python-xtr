"""The bundle's wiring of its optional peers: the HTTP client, the event dispatcher, the bus.

Each peer reaches the services through a holder that is always registered, so a
service takes the same parameters whether its peer is active or not.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_dependency_injection import (
    ContainerBuilder,
    ServiceConfigurator,
    bundle_active,
    named_factory,
)

from xtr_notifier.message import ChatMessage, PushMessage, SmsMessage
from xtr_notifier.transport import AbstractTransportFactory

from ._peers import EventDispatcherPeer, HttpClientPeer, MessageBusPeer
from ._services import tagged_factory
from .notifier_config import NotifierConfig

if TYPE_CHECKING:
    from collections.abc import Hashable

__all__ = ["build_from_peers", "register_peers"]


def build_from_peers(builder: ContainerBuilder, key: tuple[type, Hashable | None]) -> None:
    """Build a tagged factory from the peers when it keeps the inherited constructor.

    Such a factory takes exactly what a discovered one is handed, so it is built
    the same way. One declaring a constructor of its own — for a collaborator
    beyond those — is left to the container.
    """
    definition = builder.get_definition(*key)
    provider = definition.provider
    if (
        definition.kind == "class"
        and isinstance(provider, type)
        and issubclass(provider, AbstractTransportFactory)
        and provider.__init__ is AbstractTransportFactory.__init__
    ):
        definition.provider = tagged_factory(provider)
        definition.kind = "factory"


def register_peers(
    config: NotifierConfig, services: ServiceConfigurator, builder: ContainerBuilder
) -> None:
    """Register the holders of the HTTP client, the event dispatcher and the bus per message."""
    if bundle_active(builder, "http_client"):
        from ._peer_factories import http_client_peer  # noqa: PLC0415 -- names an optional peer

        _ = services.set(named_factory(http_client_peer(config.http_client), "notifier_http"))
    else:
        _ = services.instance(HttpClientPeer(None))
    if bundle_active(builder, "event_dispatcher"):
        from ._peer_factories import event_dispatcher_peer  # noqa: PLC0415 -- as above

        _ = services.set(event_dispatcher_peer)
    else:
        _ = services.instance(EventDispatcherPeer(None))
    queued = _queued_kinds(builder)
    for name in ("chat", "sms", "push", "texter"):
        if name in queued:
            from ._message_bus import message_bus_peer  # noqa: PLC0415 -- xtr-messenger is optional

            _ = services.set(
                named_factory(message_bus_peer, f"notifier_{name}_bus"), qualifier=name
            )
        else:
            _ = services.instance(MessageBusPeer(None), qualifier=name)


def _queued_kinds(builder: ContainerBuilder) -> frozenset[str]:
    """Return which senders queue on the bus: those whose messages the bus routes.

    The texter sends both SMS and push messages, so it queues only when both
    are routed; otherwise one of them would be dropped by the bus.
    """
    if not bundle_active(builder, "messenger"):
        return frozenset()
    from xtr_messenger import MessageBusConfig  # noqa: PLC0415 -- xtr-messenger is optional

    from ._message_bus import routed  # noqa: PLC0415 -- as above

    bus = builder.get_extension_config(MessageBusConfig)
    queued = {
        name
        for name, message_type in (
            ("chat", ChatMessage),
            ("sms", SmsMessage),
            ("push", PushMessage),
        )
        if routed(bus, message_type)
    }
    if {"sms", "push"} <= queued:
        queued.add("texter")
    return frozenset(queued)
