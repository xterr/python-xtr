"""End to end: an application whose messages go through a table on its own database."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from xtr_dependency_injection import Kernel
from xtr_messenger import MessageBusInterface, WorkerFactory
from xtr_orm import Migrator

from tests.fixtures.app_orm_messenger.handlers import Ledger
from tests.fixtures.app_orm_messenger.messages import QueuedOrder

if TYPE_CHECKING:
    from xtr_service_contracts import ContainerInterface

pytestmark = pytest.mark.anyio

_APP = "tests.fixtures.app_orm_messenger"


def _kernel(root: Path) -> Kernel:
    root.mkdir(parents=True, exist_ok=True)
    return Kernel(
        _APP,
        env="test",
        environ={
            "ORM_TEST_URL": f"sqlite+aiosqlite:///{root / 'app.sqlite'}",
            "ORM_TEST_MIGRATIONS": str(root / "migrations"),
        },
    )


async def _drain(container: ContainerInterface, expected: int) -> list[str]:
    """Run a worker on ``orders`` until it handled ``expected`` orders, then stop it."""
    ledger = await container.get(Ledger)
    worker = (await container.get(WorkerFactory)).worker(["orders"])
    running = asyncio.ensure_future(worker.run())
    try:
        async with asyncio.timeout(5):
            while len(ledger.orders) < expected:
                _ = await ledger.recorded.wait()
                ledger.recorded.clear()
    finally:
        worker.stop()
        await running
    return ledger.orders


async def test_a_queued_message_is_handled_by_a_worker_and_leaves_the_table(
    tmp_path: Path,
) -> None:
    async with await _kernel(tmp_path).boot() as booted:
        container = booted.container
        bus = await container.get(MessageBusInterface)
        _ = await bus.dispatch(QueuedOrder("o-1"))
        _ = await bus.dispatch(QueuedOrder("o-2"))
        assert (await container.get(Ledger)).orders == []

        handled = await _drain(container, 2)

    assert handled == ["o-1", "o-2"]


async def test_the_messages_table_is_written_by_the_connections_next_revision(
    tmp_path: Path,
) -> None:
    async with await _kernel(tmp_path).boot() as booted:
        written = await (await booted.container.get(Migrator)).diff("messages")

    assert written is not None
    body = Path(written.path).read_text(encoding="utf-8")
    assert "op.create_table('messenger_messages'" in body
    assert "messenger_messages_queue_name_idx" in body
