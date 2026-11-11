from __future__ import annotations

from importlib.util import find_spec
from typing import TYPE_CHECKING

import pytest
from advanced_alchemy.base import metadata_registry
from pydantic_ai import Agent, CancellationToken
from pydantic_ai.conversation import Conversation
from pydantic_ai.conversation_store import ConversationStore
from pydantic_ai.models.test import TestModel
from sqlalchemy.ext.asyncio import AsyncEngine
from xtr_dependency_injection import Kernel

from tests.fixtures.app_ai_orm.config import BIND_KEY, URL_VARIABLE
from xtr_ai import RunState
from xtr_ai.exception import InvalidConfigurationError
from xtr_ai.run_control_interface import RunControlInterface

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.anyio


def _kernel(tmp_path: Path) -> Kernel:
    return Kernel(
        "tests.fixtures.app_ai_orm",
        env="test",
        environ={URL_VARIABLE: f"sqlite+aiosqlite:///{tmp_path / 'ai.sqlite'}"},
    )


async def test_the_bridges_tables_join_the_connections_definitions(tmp_path: Path) -> None:
    async with await _kernel(tmp_path).boot():
        tables = set(metadata_registry.get(BIND_KEY).tables)

    assert {"ai_conversation", "ai_conversation_entry", "ai_run"} <= tables


async def test_conversations_and_runs_are_kept_in_the_database(tmp_path: Path) -> None:
    async with await _kernel(tmp_path).boot() as booted:
        engine = await booted.container.get(AsyncEngine)
        async with engine.begin() as connection:
            await connection.run_sync(metadata_registry.get(BIND_KEY).create_all)
        store = await booted.container.get(ConversationStore)
        control = await booted.container.get(RunControlInterface)

        _ = await control.start("r1", agent="chat", conversation_id="c1")
        async with control.watch("r1", CancellationToken()):
            result = await Agent(TestModel()).run(
                "hi", conversation=Conversation(conversation_id="c1")
            )
            _ = await store.save(result)

        loaded = await store.load("c1")
        status = await control.get("r1")

    assert loaded is not None
    assert len(loaded.messages) == 2
    assert status is not None
    assert status.state is RunState.FINISHED


async def test_an_orm_adapter_without_its_bridge_names_the_package(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def hidden(name: str) -> object:
        return None if name.startswith("xtr_ai_orm") else find_spec(name)

    monkeypatch.setattr("xtr_ai.bundle._references.find_spec", hidden)
    monkeypatch.setattr("xtr_ai.bundle.ai_bundle.find_spec", hidden)

    with pytest.raises(InvalidConfigurationError, match=r'uv add "xtr-ai\[orm\]"'):
        _ = await _kernel(tmp_path).boot()


async def test_an_orm_adapter_without_the_orm_bundle_names_both() -> None:
    with pytest.raises(InvalidConfigurationError, match="OrmBundle is not active"):
        _ = await Kernel("tests.fixtures.app_ai_orm_inactive", env="test").boot()


async def test_the_orm_bundle_is_left_to_the_application() -> None:
    async with await Kernel("tests.fixtures.app_ai", env="test").boot() as booted:
        active = booted.container.get_parameter("kernel.bundles")

    assert isinstance(active, dict)
    assert "orm" not in active
