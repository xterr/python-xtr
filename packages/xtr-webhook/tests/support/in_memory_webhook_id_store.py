"""A webhook id store kept in a dictionary, for the controller's tests."""

from __future__ import annotations

from typing import final

from typing_extensions import override

from xtr_webhook.client.webhook_id_store_interface import WebhookIdStoreInterface

__all__ = ["InMemoryWebhookIdStore"]


@final
class InMemoryWebhookIdStore(WebhookIdStoreInterface):
    """Remembers ids for as long as the test runs, recording the lifetime each was asked for."""

    def __init__(self) -> None:
        self.ttls: dict[str, int] = {}

    @override
    async def remember(self, webhook_id: str, ttl: int) -> bool:
        if webhook_id in self.ttls:
            return False
        self.ttls[webhook_id] = ttl
        return True

    @override
    async def forget(self, webhook_id: str) -> None:
        _ = self.ttls.pop(webhook_id, None)
