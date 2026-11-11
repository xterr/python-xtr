from __future__ import annotations

import pytest
from pydantic_ai.conversation_store import ConversationStore
from xtr_dependency_injection import Kernel

from tests.fixtures.app_ai_services.config import ArchiveStore, OwnRunControl
from xtr_ai.run_control_interface import RunControlInterface

pytestmark = pytest.mark.anyio


async def test_the_applications_own_store_and_run_control_are_injected() -> None:
    async with await Kernel("tests.fixtures.app_ai_services", env="test").boot() as booted:
        store = await booted.container.get(ConversationStore, "archive")
        own = await booted.container.get(ArchiveStore)
        run_control = await booted.container.get(RunControlInterface)
        registered = await booted.container.get(OwnRunControl)

    assert store is own
    assert run_control is registered
