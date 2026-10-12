"""The httpx side of the bundle: the client, the sender and the transport.

Imported by the bundle only after it checked the client library is installed:
httpx sits at the top of this module, so the bundle itself stays importable
without the ``client`` extra, and nothing here runs until it is.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from typing import Annotated, Final

import httpx
from xtr_dependency_injection import ServiceConfigurator, Target, named_factory

from xtr_webhook.bridge.httpx import HttpxSender, NoPrivateNetworkTransport
from xtr_webhook.server.header_signature_configurator import HeaderSignatureConfigurator
from xtr_webhook.server.headers_configurator import HeadersConfigurator
from xtr_webhook.server.json_body_configurator import JsonBodyConfigurator
from xtr_webhook.server.transport import Transport
from xtr_webhook.server.transport_interface import TransportInterface

from .webhook_config import WebhookConfig

__all__ = ["register"]

_WEBHOOK: Final = "webhook"
"""The qualifier of the client the bundle builds and owns."""

_TIMEOUT_SECONDS: Final = 30.0
"""A bound on every delivery: a receiver that never answers must not hold a worker."""


def register(config: WebhookConfig, services: ServiceConfigurator) -> None:
    """Register what delivers a webhook: the client, the sender over it, the transport.

    The client is the application's when ``http_client`` names one it
    registered; otherwise the bundle builds its own, wrapped in the
    private-network guard when the configuration turns it on. Nothing is
    opened here: the client is built when a delivery first needs it.
    """
    client_qualifier = config.http_client
    if client_qualifier is None:
        client_qualifier = _WEBHOOK
        _ = services.set(named_factory(_bundle_client, "webhook_http_client"), qualifier=_WEBHOOK)
    _ = services.set(named_factory(_http_sender(client_qualifier), "webhook_http_sender"))
    _ = services.set(named_factory(_transport, "webhook_transport"))
    services.alias(TransportInterface, Transport)


async def _bundle_client(config: WebhookConfig) -> AsyncIterator[httpx.AsyncClient]:
    """Build the bundle's own client, and close it when the container closes.

    The configuration is injected rather than closed over: the container
    hands the factory a copy with every environment placeholder resolved.
    """
    guard = config.no_private_network
    transport = (
        NoPrivateNetworkTransport(httpx.AsyncHTTPTransport(), guard.subnets, guard.allow_list)
        if guard.enabled
        else None
    )
    client = httpx.AsyncClient(timeout=httpx.Timeout(_TIMEOUT_SECONDS), transport=transport)
    try:
        yield client
    finally:
        await client.aclose()


def _http_sender(qualifier: str) -> Callable[..., HttpxSender]:
    """Return the factory of the sender, over the client ``qualifier`` names.

    The qualifier is configuration, so the parameter's annotation is written
    onto the factory at runtime rather than in its signature.
    """

    def build(client: httpx.AsyncClient) -> HttpxSender:
        return HttpxSender(client)

    build.__annotations__ = {
        "client": Annotated[httpx.AsyncClient, Target(qualifier)],
        "return": HttpxSender,
    }
    return build


def _transport(
    sender: HttpxSender,
    headers: HeadersConfigurator,
    body: JsonBodyConfigurator,
    signer: HeaderSignatureConfigurator,
) -> Transport:
    """Build the delivery over the sender and the configurator chain the bundle registered."""
    return Transport(sender, headers, body, signer)
