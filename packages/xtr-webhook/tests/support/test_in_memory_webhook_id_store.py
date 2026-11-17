"""The fake id store keeps the contract the controller relies on."""

from __future__ import annotations

import pytest

from tests.support.in_memory_webhook_id_store import InMemoryWebhookIdStore
from xtr_webhook.client.webhook_id_store_interface import WebhookIdStoreInterface

pytestmark = pytest.mark.anyio


def test_it_is_a_webhook_id_store() -> None:
    assert isinstance(InMemoryWebhookIdStore(), WebhookIdStoreInterface)


async def test_only_the_first_remember_of_an_id_answers_true() -> None:
    store = InMemoryWebhookIdStore()

    assert await store.remember("a", 60) is True
    assert await store.remember("a", 60) is False
    assert await store.remember("b", 60) is True


async def test_a_forgotten_id_is_remembered_afresh() -> None:
    store = InMemoryWebhookIdStore()
    _ = await store.remember("a", 60)

    await store.forget("a")

    assert await store.remember("a", 60) is True
