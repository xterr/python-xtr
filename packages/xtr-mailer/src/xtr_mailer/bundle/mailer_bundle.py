"""The xtr-mailer bundle: the mailer, its transports and its listeners, from one config.

An application listing :class:`MailerBundle` gets a :class:`~xtr_mailer.MailerInterface` and a
:class:`~xtr_mailer.transport.TransportInterface` — the configured transports by name — whatever
it configures; with nothing configured, every email is discarded. No DSN is read, and nothing
is reached, before the first email is sent; the transports' sessions end when the container
closes.

The peers are optional, each wired only when its bundle is active: the HTTP client provider
transports talk through, the event dispatcher the listeners hear every email on, the message
bus email is queued on, the rate limiters capping the transports and the console the
``mailer:test`` command runs in.
"""

from __future__ import annotations

from importlib.util import find_spec
from typing import Final, final

from typing_extensions import override
from xtr_dependency_injection import (
    Bundle,
    ContainerBuilder,
    ServiceConfigurator,
    as_bundle,
    bundle_active,
    named_factory,
    required_bundle,
)

from xtr_mailer._error_text import shown
from xtr_mailer.exception import LogicError
from xtr_mailer.mailer import Mailer
from xtr_mailer.mailer_interface import MailerInterface
from xtr_mailer.transport import TransportFactoryInterface, TransportInterface, Transports

from ._listeners import register_listeners
from ._peers import EventDispatcherPeer, HttpClientPeer, MessageBusPeer, RateLimitersPeer
from ._services import (
    TAGGED_FACTORY_PREFIX,
    mailer,
    mailer_transports,
    transport_factory_discovery,
)
from .mailer_config import MailerConfig

__all__ = ["MAILER_TRANSPORT_FACTORY_TAG", "MailerBundle"]

#: Tags a transport factory the mailer tries before the installed ones, in tag order.
MAILER_TRANSPORT_FACTORY_TAG: Final = "mailer.transport_factory"

_EXTRAS: Final = {
    "dkim": ("DKIM", ("dkim", "cryptography")),
    "smime": ("S/MIME", ("cryptography",)),
}
"""Each extra by name: what it is used for, and the modules it installs."""


@final
@required_bundle("xtr_event_dispatcher.bundle:EventDispatcherBundle", ignore_on_invalid=True)
@required_bundle("xtr_messenger.bundle:MessengerBundle", ignore_on_invalid=True)
@required_bundle("xtr_http_client.bundle:HttpClientBundle", ignore_on_invalid=True)
@required_bundle("xtr_rate_limiter.bundle:RateLimiterBundle", ignore_on_invalid=True)
@required_bundle("xtr_console.bundle:ConsoleBundle", ignore_on_invalid=True)
@as_bundle("mailer", config=MailerConfig)
class MailerBundle(Bundle[MailerConfig]):
    """Wires the mailer, its transports, its listeners and its command to the container."""

    @override
    def load_extension(
        self,
        config: MailerConfig,
        services: ServiceConfigurator,
        builder: ContainerBuilder,
    ) -> None:
        """Register the mailer and its transports, and wire each active peer.

        Raises:
            LogicError: A transport is capped by a rate limiter without the rate limiter
                bundle, an option needs the event dispatcher bundle and it is inactive, or
                signing or encrypting is configured without its extra.
        """
        _require_extras(config)
        _register_peers(config, services, builder)
        _ = services.set(transport_factory_discovery)
        _ = services.set(named_factory(mailer_transports, "mailer_transports"))
        services.alias(TransportInterface, Transports)
        _ = services.set(mailer)
        services.alias(MailerInterface, Mailer)
        register_listeners(config, services, builder)
        if bundle_active(builder, "messenger"):
            services.load("xtr_mailer.bundle._send_email_message_handler")
        if bundle_active(builder, "console"):
            services.load("xtr_mailer.command")

    @override
    def process(self, builder: ContainerBuilder) -> None:
        """Offer the factories tagged :data:`MAILER_TRANSPORT_FACTORY_TAG` to the transports."""
        tagged = builder.find_tagged_service_ids(MAILER_TRANSPORT_FACTORY_TAG)
        for index, (service, qualifier) in enumerate(tagged):
            builder.set_alias(
                TransportFactoryInterface,
                service,
                alias_qualifier=f"{TAGGED_FACTORY_PREFIX}{index}",
                target_qualifier=qualifier,
            )


def _register_peers(
    config: MailerConfig, services: ServiceConfigurator, builder: ContainerBuilder
) -> None:
    """Register the holders of the HTTP client, the event dispatcher, the bus and the limiters.

    Raises:
        LogicError: A transport is capped by a rate limiter without the rate limiter bundle.
    """
    if bundle_active(builder, "http_client"):
        from ._peer_factories import http_client_peer  # noqa: PLC0415 -- names an optional peer

        _ = services.set(named_factory(http_client_peer(config.http_client), "mailer_http"))
    else:
        _ = services.instance(HttpClientPeer(None))
    if bundle_active(builder, "event_dispatcher"):
        from ._peer_factories import event_dispatcher_peer  # noqa: PLC0415 -- as above

        _ = services.set(event_dispatcher_peer)
    else:
        _ = services.instance(EventDispatcherPeer(None))
    _register_message_bus(services, builder)
    if bundle_active(builder, "rate_limiter"):
        from ._rate_limiters import rate_limiters_peer  # noqa: PLC0415 -- as above

        _ = services.set(rate_limiters_peer)
    else:
        _refuse_rate_limiters(config)
        _ = services.instance(RateLimitersPeer(None))


def _register_message_bus(services: ServiceConfigurator, builder: ContainerBuilder) -> None:
    """Queue email on the bus when the messenger bundle is active and the bus routes it."""
    if bundle_active(builder, "messenger"):
        from xtr_messenger import MessageBusConfig  # noqa: PLC0415 -- xtr-messenger is optional

        from ._message_bus import message_bus_peer, routed  # noqa: PLC0415 -- as above

        if routed(builder.get_extension_config(MessageBusConfig)):
            _ = services.set(message_bus_peer)
            return
    _ = services.instance(MessageBusPeer(None))


def _refuse_rate_limiters(config: MailerConfig) -> None:
    """Refuse a transport capped by a rate limiter while there are no rate limiters.

    Raises:
        LogicError: A transport names a rate limiter.
    """
    for name, transport in config.get_transports().items():
        if transport.rate_limiter is not None:
            raise LogicError(
                f'The "{shown(name)}" transport is capped by the "{shown(transport.rate_limiter)}" '
                "rate limiter; install xtr-rate-limiter beside xtr-mailer and configure the "
                "limiter."
            )


def _require_extras(config: MailerConfig) -> None:
    """Refuse signing or encrypting without the extra doing it, naming the mailer's extra.

    Raises:
        LogicError: DKIM or S/MIME is configured and its extra is not installed.
    """
    needed = {
        "dkim": config.dkim_signer is not None,
        "smime": config.smime_signer is not None or config.smime_encrypter is not None,
    }
    for extra, (label, modules) in _EXTRAS.items():
        if needed[extra] and any(find_spec(module) is None for module in modules):
            raise LogicError(
                f'The "{extra}" extra is required to use {label}: uv add "xtr-mailer[{extra}]".'
            )
