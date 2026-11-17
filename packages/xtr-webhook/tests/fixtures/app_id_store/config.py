"""Name the application's id store, remembered for ten minutes."""

from __future__ import annotations

from xtr_dependency_injection import configure

from tests.support.in_memory_webhook_id_store import InMemoryWebhookIdStore
from xtr_webhook.bundle import WebhookConfig

ID_TTL = 600
"""How long the application remembers an id."""


@configure
def webhook() -> WebhookConfig:
    """Remember the ids of the webhooks taken, for ten minutes."""
    return WebhookConfig(id_store=InMemoryWebhookIdStore, id_ttl=ID_TTL)
