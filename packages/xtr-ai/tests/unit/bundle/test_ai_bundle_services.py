from __future__ import annotations

import pytest
from pydantic_ai.conversation_store import ConversationStore
from xtr_dependency_injection import Kernel

from tests.fixtures.app_ai_services.config import ArchiveStore

pytestmark = pytest.mark.anyio


async def test_the_applications_own_store_is_injected() -> None:
    async with await Kernel("tests.fixtures.app_ai_services", env="test").boot() as booted:
        store = await booted.container.get(ConversationStore, "archive")
        own = await booted.container.get(ArchiveStore)

    assert store is own
