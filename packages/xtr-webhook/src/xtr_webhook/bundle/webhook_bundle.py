"""The xtr-webhook bundle: the receiving endpoint and the signing sender, from one config.

An application listing :class:`WebhookBundle` — which brings the remote-event
and messenger bundles with it, and the HTTP kernel's when that package is
installed — gets the controller behind ``routes()``, a configured
:class:`~xtr_webhook.client.RequestParser` under the ``webhook`` qualifier,
and — when the httpx client library is installed — the transport that delivers
a ``SendWebhookMessage`` and the handler that listens for one. The handler is
registered only alongside the transport it needs, so a container never holds a
handler it cannot build; without the ``client`` extra, dispatching a
``SendWebhookMessage`` fails with the bus's no-handler error.
"""

from __future__ import annotations

from importlib.util import find_spec
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

from .webhook_config import WebhookConfig

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

__all__ = ["WebhookBundle"]

_WEBHOOK: Final = "webhook"
"""The qualifier of the bundle's own parser and its own client."""

_NO_CONTAINER: Final = "the webhook bundle has no container; it is used before it booted"

_SEND_HANDLER_MODULE: Final = "xtr_webhook.messenger.send_webhook_handler"


@final
@required_bundle(RemoteEventBundle)
@required_bundle("xtr_http_kernel.bundle:HttpKernelBundle", ignore_on_invalid=True)
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
        """Register the configurators, the parser, the controller and the httpx side.

        The format is converted once, here: the configurators and the parser
        take a member, and every factory below is handed the same one.
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

        _ = services.set(named_factory(_webhook_controller(self), "webhook_controller"))

        if find_spec("httpx") is not None:
            # Imported only now: httpx sits at the top of that module, and is
            # only installed with the client extra.
            from xtr_webhook.bundle._http_client import (  # noqa: PLC0415 -- guarded behind the client extra
                register,
            )

            register(config, services)
            # The handler needs the transport registered just above, so it is
            # registered with the bus only here: a container must never hold a
            # handler it cannot build.
            services.load(_SEND_HANDLER_MODULE)


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
    bundle: WebhookBundle,
) -> Callable[[WebhookConfig, MessageBusInterface], Coroutine[None, None, WebhookController]]:
    """Return the factory serving the endpoint's controller over the routed parsers.

    The parsers go in as a :class:`ServiceLocator`, so the controller never
    holds the container and a route's parser is built — with its
    dependencies — only when the first webhook for it arrives. A route naming
    no parser falls back to the bundle's own, under its ``webhook`` qualifier.
    """

    async def build(config: WebhookConfig, bus: MessageBusInterface) -> WebhookController:
        container = bundle.container
        if container is None:
            raise LogicError(_NO_CONTAINER)
        parsers = ServiceLocator[RequestParserInterface](
            container,
            {
                name: (route.parser, None)
                if route.parser is not None
                else (RequestParser, _WEBHOOK)
                for name, route in config.routing.items()
            },
        )
        secrets = {name: route.secret for name, route in config.routing.items()}
        return WebhookController(parsers, secrets, bus)

    return build
