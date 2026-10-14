"""The guard turned on around the client the application named for its webhooks."""

from __future__ import annotations

from xtr_dependency_injection import configure
from xtr_http_client.bundle import HttpClientConfig, ScopedClientConfig
from xtr_messenger import MessageBusConfig, TransportConfig

from xtr_webhook.bundle import NoPrivateNetworkConfig, WebhookConfig
from xtr_webhook.messenger import SendWebhookMessage

GUARDED_CLIENT = "outbound"
"""The client the guard wraps: a named one, since any client can be guarded."""


@configure
def webhook() -> WebhookConfig:
    """Send through the named client, with the private-network guard turned on."""
    return WebhookConfig(
        http_client=GUARDED_CLIENT,
        no_private_network=NoPrivateNetworkConfig(enabled=True),
    )


@configure
def http_client() -> HttpClientConfig:
    """Name the client, and answer from the mock transport whatever gets past the guard."""
    return HttpClientConfig(
        mock_response_factory=True,
        scoped_clients={GUARDED_CLIENT: ScopedClientConfig(scope="https?://")},
    )


@configure
def messenger() -> MessageBusConfig:
    """Route the send message to ``sync://``, so a refused delivery fails the dispatch."""
    return MessageBusConfig(
        transports={"sync": TransportConfig("sync://")},
        routing={SendWebhookMessage: "sync"},
    )
