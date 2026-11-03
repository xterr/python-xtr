"""The services the mailer bundle has the container build.

Each factory's parameters are read at runtime by the container, so the types they name are
imported here, not only for type checking.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping, Sequence
from typing import Final

from xtr_dependency_injection import ServiceLocator
from xtr_mime.header import Headers

from xtr_mailer.event_listener import EnvelopeListener, MessageListener, MessageLoggerListener
from xtr_mailer.header import TrackingHeader
from xtr_mailer.mailer import Mailer
from xtr_mailer.transport import (
    Transport,
    TransportFactoryDiscovery,
    TransportFactoryInterface,
    TransportInterface,
    Transports,
)

from ._peers import (
    EventDispatcherPeer,
    HttpClientPeer,
    LoggerPeer,
    MessageBusPeer,
    RateLimitersPeer,
)
from .envelope_config import EnvelopeConfig
from .mailer_config import MailerConfig
from .tracking_config import TrackingConfig

__all__ = [
    "TAGGED_FACTORY_PREFIX",
    "envelope_listener",
    "mailer",
    "mailer_transports",
    "message_listener",
    "message_logger_listener",
    "transport_factory_discovery",
]

#: What the qualifiers of the transport factories an application tags start with.
TAGGED_FACTORY_PREFIX: Final = "mailer.transport_factory."


def transport_factory_discovery(
    http_client: HttpClientPeer, event_dispatcher: EventDispatcherPeer, logger: LoggerPeer
) -> TransportFactoryDiscovery:
    """Find the installed factories, each handed the HTTP client, the dispatcher and the logger."""
    return TransportFactoryDiscovery(
        event_dispatcher=event_dispatcher.event_dispatcher,
        http_client=http_client.http_client,
        logger=logger.logger,
    )


async def mailer_transports(
    config: MailerConfig,
    factories: ServiceLocator[TransportFactoryInterface],
    discovery: TransportFactoryDiscovery,
    rate_limiters: RateLimitersPeer,
    logger: LoggerPeer,
) -> AsyncIterator[Transports]:
    """Build the configured transports, and end their sessions when the container closes.

    The DSNs are read here, on first use — never at build or boot — so a DSN given through
    ``env()`` is checked where it is used. The rate limiters are fetched first, since the
    transports are built without awaiting. The factories an application tagged are tried
    before the installed ones, in tag order. A ``failover(...)`` or ``roundrobin(...)`` group
    logs each member that fails through ``logger``; the members log through the factory that
    built them.

    Raises:
        LogicError: A transport names a rate limiter that is not configured, or one that cannot
            cap it — a ``failover(...)`` or ``roundrobin(...)`` group is never capped.
        InvalidArgumentError: A DSN cannot be read.
        UnsupportedSchemeError: No factory serves a scheme a DSN names.
    """
    configured = config.get_transports()
    capping = await rate_limiters.capping(
        {
            name: transport.rate_limiter
            for name, transport in configured.items()
            if transport.rate_limiter is not None
        }
    )
    tagged = sorted(
        (
            key
            for key in factories.provided_services()
            if isinstance(key, str) and key.startswith(TAGGED_FACTORY_PREFIX)
        ),
        key=lambda key: int(key.removeprefix(TAGGED_FACTORY_PREFIX)),
    )
    builder = Transport(
        [await factories.get(key) for key in tagged],
        discovery,
        rate_limiter_factories=capping,
        logger=logger.logger,
    )
    transports = builder.from_strings({name: item.dsn for name, item in configured.items()})
    try:
        yield transports
    finally:
        await transports.close()


def mailer(
    transport: TransportInterface,
    message_bus: MessageBusPeer,
    event_dispatcher: EventDispatcherPeer,
) -> Mailer:
    """Build the mailer, queuing on the bus when the bus routes queued email."""
    return Mailer(transport, message_bus.message_bus, event_dispatcher.event_dispatcher)


def message_logger_listener() -> MessageLoggerListener:
    """Build the listener recording every email event, recording at all times."""
    return MessageLoggerListener()


def envelope_listener(envelope: EnvelopeConfig) -> EnvelopeListener:
    """Build the listener giving every email the configured envelope."""
    return EnvelopeListener(
        envelope.sender, envelope.recipients or None, envelope.allowed_recipients
    )


def message_listener(
    headers: Mapping[str, str | Sequence[str]], tracking: TrackingConfig
) -> MessageListener:
    """Build the listener giving every email the configured headers.

    Tracking adds an ``X-Track`` header, unless one is among the configured headers.
    """
    defaults = Headers()
    for name, value in headers.items():
        _ = defaults.add_header(name, value if isinstance(value, str) else list(value))
    if tracking.is_configured() and not defaults.has(TrackingHeader.NAME):
        _ = defaults.add(TrackingHeader(tracking.opens, tracking.clicks))
    return MessageListener(defaults)
