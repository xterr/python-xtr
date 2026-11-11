from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

import anyio
import pytest
from pydantic_ai import CancellationToken
from sqlalchemy import MetaData
from typing_extensions import override
from xtr_ai.testing.run_control_contract import CONTRACT_POLL_INTERVAL, RunControlContract

from tests.conftest import open_database
from xtr_ai_orm_run_control import OrmRunControl, RunMappingDriver

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator
    from pathlib import Path

    from xtr_clock import MockClock


class TestOrmRunControl(RunControlContract):
    @pytest.fixture(autouse=True)
    def _database(self, tmp_path: Path) -> None:
        self._path: Path = tmp_path / "ai.sqlite"

    @override
    @asynccontextmanager
    async def build(self, clock: MockClock) -> AsyncGenerator[OrmRunControl]:
        engine = await open_database(self._path)
        try:
            yield OrmRunControl(engine, clock=clock, cancel_poll_interval=CONTRACT_POLL_INTERVAL)
        finally:
            await engine.dispose()


@pytest.mark.anyio
async def test_a_cancellation_from_another_process_reaches_the_watching_one(
    tmp_path: Path,
) -> None:
    path = tmp_path / "ai.sqlite"
    watching_engine = await open_database(path)
    other_engine = await open_database(path)
    try:
        watching = OrmRunControl(watching_engine, cancel_poll_interval=0.01)
        other = OrmRunControl(other_engine, cancel_poll_interval=0.01)
        _ = await watching.start("r1", agent="chat", conversation_id="c1")
        token = CancellationToken()

        async with watching.watch("r1", token):
            assert await other.request_cancel("r1")
            with anyio.fail_after(2):
                while not token.cancelled:  # noqa: ASYNC110 — the token offers no event
                    await anyio.sleep(0.01)

        status = await other.get("r1")
        assert status is not None
        assert status.cancel_requested
    finally:
        await watching_engine.dispose()
        await other_engine.dispose()


def test_the_table_is_added_once() -> None:
    metadata = MetaData()
    driver = RunMappingDriver()

    assert driver.load_metadata(metadata) == ("ai_run",)
    assert driver.load_metadata(metadata) == ()
