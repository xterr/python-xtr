"""The guard turned on, and no client of the application's own to conflict with it."""

from __future__ import annotations

from xtr_dependency_injection import configure
from xtr_messenger import MessageBusConfig, TransportConfig

from xtr_webhook.bundle import NoPrivateNetworkConfig, WebhookConfig
from xtr_webhook.messenger import SendWebhookMessage


@configure
def webhook() -> WebhookConfig:
    """Turn the private-network guard on for the bundle-built client."""
    return WebhookConfig(no_private_network=NoPrivateNetworkConfig(enabled=True))


@configure
def messenger() -> MessageBusConfig:
    """Route the send message to ``sync://``, so a refused delivery fails the dispatch."""
    return MessageBusConfig(
        transports={"sync": TransportConfig("sync://")},
        routing={SendWebhookMessage: "sync"},
    )
