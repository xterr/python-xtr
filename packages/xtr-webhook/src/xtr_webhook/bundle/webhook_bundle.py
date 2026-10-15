"""The xtr-webhook bundle: the receiving endpoint and the signing sender, from one config.

An application listing :class:`WebhookBundle` — which brings the remote-event,
messenger and HTTP kernel bundles with it, and the HTTP client bundle when
xtr-http-client is installed — gets the endpoint webhooks arrive at, which
``setup`` mounts, and its controller, a configured
:class:`~xtr_webhook.client.RequestParser` under the ``webhook`` qualifier,
and — with xtr-http-client — the transport that delivers a
``SendWebhookMessage`` and the handler that listens for one. The handler is
registered only alongside the transport it needs, so a container never holds a
handler it cannot build; without xtr-http-client installed, dispatching a
``SendWebhookMessage`` fails with the bus's no-handler error.
"""

from __future__ import annotations

from importlib.util import find_spec
from typing import TYPE_CHECKING, Annotated, Final, final

from typing_extensions import override
from xtr_dependency_injection import (
    Bundle,
    ContainerBuilder,
    ServiceConfigurator,
    ServiceLocator,
    Target,
    as_bundle,
    named_factory,
    required_bundle,
)
from xtr_http_client_contracts import HttpClientInterface
from xtr_http_kernel.bundle import HttpKernelBundle
from xtr_messenger import MessageBusInterface
from xtr_remote_event.bundle import RemoteEventBundle

from xtr_webhook.client.request_parser import RequestParser
from xtr_webhook.client.request_parser_interface import RequestParserInterface
from xtr_webhook.controller.webhook_controller import WebhookController
from xtr_webhook.exception import LogicError
from xtr_webhook.server.header_signature_configurator import HeaderSignatureConfigurator
from xtr_webhook.server.headers_configurator import HeadersConfigurator
from xtr_webhook.server.json_body_configurator import JsonBodyConfigurator
from xtr_webhook.server.json_payload_serializer import JsonPayloadSerializer
from xtr_webhook.server.signature_format import SignatureFormat
from xtr_webhook.server.transport import Transport
from xtr_webhook.server.transport_interface import TransportInterface

from ._routed_parsers import ROUTE_QUALIFIER, RoutedParsers
from .webhook_config import WebhookConfig

if TYPE_CHECKING:
    from collections.abc import Callable

__all__ = ["WebhookBundle"]

_WEBHOOK: Final = "webhook"
"""The qualifier of the bundle's own parser."""

_SEND_HANDLER_MODULE: Final = "xtr_webhook.messenger.send_webhook_handler"

_ROUTING_MODULE: Final = "xtr_webhook.routing"


@final
@required_bundle(RemoteEventBundle)
@required_bundle(HttpKernelBundle)
@required_bundle("xtr_http_client.bundle:HttpClientBundle", ignore_on_invalid=True)
@as_bundle("webhook", config=WebhookConfig)
class WebhookBundle(Bundle[WebhookConfig]):
    """Wires the endpoint's controller and the sender's chain to the container."""

    @override
    def load_extension(
        self,
        config: WebhookConfig,
        services: ServiceConfigurator,
        builder: ContainerBuilder,
    ) -> None:
        """Register the configurators, the parser, the controller and the sending side.

        The format is converted once, here: the configurators and the parser
        take a member, and every factory below is handed the same one.

        Raises:
            LogicError: When the private-network guard is turned on while
                xtr-http-client, whose client it wraps, is not installed.
        """
        del builder
        fmt = SignatureFormat.parse(config.signature_format)

        _ = services.set(named_factory(_headers_configurator(fmt), "webhook_headers_configurator"))
        _ = services.set(named_factory(_json_body_configurator(fmt), "webhook_body_configurator"))
        _ = services.set(named_factory(_signer(fmt), "webhook_signer"))

        _ = services.set(
            named_factory(_request_parser(fmt), "webhook_request_parser"), qualifier=_WEBHOOK
        )
        services.alias(
            RequestParserInterface,
            RequestParser,
            alias_qualifier=_WEBHOOK,
            target_qualifier=_WEBHOOK,
        )
        for parser in _custom_parsers(config):
            _ = services.set(parser)
        # Each configured type's parser, under a qualifier of its own: the
        # controller reaches them through a locator the container injects.
        for name, route in config.routing.items():
            services.alias(
                RequestParserInterface,
                route.parser if route.parser is not None else RequestParser,
                alias_qualifier=ROUTE_QUALIFIER.format(type=name),
                target_qualifier=None if route.parser is not None else _WEBHOOK,
            )

        _ = services.set(named_factory(_webhook_controller, "webhook_controller"))
        # The route loader: scanned so the http kernel builds the endpoint into
        # the application's table, which setup() mounts.
        services.load(_ROUTING_MODULE)

        if find_spec("xtr_http_client") is not None:
            _ = services.set(named_factory(_transport(config.http_client), "webhook_transport"))
            services.alias(TransportInterface, Transport)
            # The handler needs the transport registered just above, so it is
            # registered with the bus only here: a container must never hold a
            # handler it cannot build.
            services.load(_SEND_HANDLER_MODULE)
        elif config.no_private_network.enabled:
            raise LogicError(
                'Configuring "no_private_network" requires xtr-http-client; '
                "install it with uv add xtr-http-client."
            )


def _custom_parsers(config: WebhookConfig) -> tuple[type[RequestParserInterface], ...]:
    """Return each distinct parser class the routing names, in first-use order.

    Distinct and once: two routes naming one class share one instance, so what
    the parser keeps between webhooks does not depend on the route they used.
    """
    seen: dict[type[RequestParserInterface], None] = {}
    for route in config.routing.values():
        if route.parser is not None:
            seen.setdefault(route.parser)
    return tuple(seen)


def _headers_configurator(fmt: SignatureFormat) -> Callable[[WebhookConfig], HeadersConfigurator]:
    """Return the factory of the step writing the identifying headers.

    The configuration is injected rather than closed over: the container
    hands the factory a copy with every environment placeholder resolved.
    """

    def build(config: WebhookConfig) -> HeadersConfigurator:
        return HeadersConfigurator(
            event_header_name=config.event_header_name,
            id_header_name=config.id_header_name,
            timestamp_header_name=config.timestamp_header_name,
            signature_format=fmt,
        )

    return build


def _json_body_configurator(fmt: SignatureFormat) -> Callable[[], JsonBodyConfigurator]:
    """Return the factory of the step writing the payload as a JSON body."""

    def build() -> JsonBodyConfigurator:
        return JsonBodyConfigurator(JsonPayloadSerializer(), fmt)

    return build


def _signer(fmt: SignatureFormat) -> Callable[[WebhookConfig], HeaderSignatureConfigurator]:
    """Return the factory of the step signing what the other two wrote."""

    def build(config: WebhookConfig) -> HeaderSignatureConfigurator:
        return HeaderSignatureConfigurator(
            algorithm=config.signing_algorithm,
            signature_header_name=config.signature_header_name,
            signature_format=fmt,
            timestamp_header_name=config.timestamp_header_name,
        )

    return build


def _transport(qualifier: str | None) -> Callable[..., Transport]:
    """Return the factory of the delivery, over the client ``qualifier`` names.

    The qualifier is configuration, so the client's annotation is written onto
    the factory at runtime rather than in its signature; ``None`` asks for the
    default client. The guard is read from the injected configuration, and
    wraps whichever client that is.
    """

    def build(
        config: WebhookConfig,
        client: HttpClientInterface,
        headers: HeadersConfigurator,
        body: JsonBodyConfigurator,
        signer: HeaderSignatureConfigurator,
    ) -> Transport:
        guard = config.no_private_network
        if guard.enabled:
            # Imported only now: the factory is registered only once
            # xtr-http-client was found, and the guard is that package's.
            from xtr_http_client import (  # noqa: PLC0415 -- xtr-http-client is optional, found above
                NoPrivateNetworkHttpClient,
            )

            client = NoPrivateNetworkHttpClient(client, guard.subnets, guard.allow_list)

        return Transport(client, headers, body, signer)

    build.__annotations__ = {
        "config": WebhookConfig,
        "client": (
            HttpClientInterface
            if qualifier is None
            else Annotated[HttpClientInterface, Target(qualifier)]
        ),
        "headers": HeadersConfigurator,
        "body": JsonBodyConfigurator,
        "signer": HeaderSignatureConfigurator,
        "return": Transport,
    }
    return build


def _request_parser(fmt: SignatureFormat) -> Callable[[WebhookConfig], RequestParser]:
    """Return the factory of the bundle's own parser, the mirror of its sender."""

    def build(config: WebhookConfig) -> RequestParser:
        return RequestParser(
            algorithm=config.signing_algorithm,
            signature_header_name=config.signature_header_name,
            event_header_name=config.event_header_name,
            id_header_name=config.id_header_name,
            timestamp_header_name=config.timestamp_header_name,
            signature_format=fmt,
            timestamp_tolerance=config.timestamp_tolerance,
        )

    return build


def _webhook_controller(
    config: WebhookConfig,
    bus: MessageBusInterface,
    parsers: ServiceLocator[RequestParserInterface],
) -> WebhookController:
    """Build the endpoint's controller over the parsers the routing names.

    The container injects a locator over every parser; only the routed types
    are handed on, each under the qualifier its route was aliased with, so a
    route's parser is built — with its dependencies — the first time a webhook
    for it arrives. A route naming no parser reads with the bundle's own.
    """
    secrets = {name: route.secret for name, route in config.routing.items()}
    return WebhookController(RoutedParsers(parsers, tuple(config.routing)), secrets, bus)
