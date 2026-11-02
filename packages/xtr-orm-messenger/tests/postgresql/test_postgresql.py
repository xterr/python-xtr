"""The transport on a real PostgreSQL server: row locks and notifications.

Skipped unless ``XTR_TEST_POSTGRES_URL`` names a database to run on, as an
asyncpg URL — ``postgresql+asyncpg://user:password@localhost/test``. Every test
uses a table of its own and drops it, so the database can be shared.
"""

from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from xtr_clock import SystemClock
from xtr_messenger import Envelope

from tests.support.connections import engine_factory
from tests.support.messages import OrderPlaced
from tests.support.serializer import SERIALIZER
from xtr_orm_messenger.transport import Connection, OrmOptions, OrmTransport

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

pytestmark = [
    pytest.mark.anyio,
    pytest.mark.skipif(
        "XTR_TEST_POSTGRES_URL" not in os.environ,
        reason="XTR_TEST_POSTGRES_URL names no PostgreSQL database to run on",
    ),
]


@pytest.fixture
async def server() -> AsyncIterator[AsyncEngine]:
    built = create_async_engine(os.environ["XTR_TEST_POSTGRES_URL"])
    yield built
    await built.dispose()


@pytest.fixture
async def options(server: AsyncEngine) -> AsyncIterator[OrmOptions]:
    table_name = f"messages_{uuid4().hex[:12]}"
    yield OrmOptions(table_name=table_name, poll_interval=30, check_delayed_interval=30_000)
    async with server.begin() as connection:
        _ = await connection.execute(text(f'DROP TABLE IF EXISTS "{table_name}"'))


def _transport(server: AsyncEngine, options: OrmOptions) -> OrmTransport:
    connection = Connection(engine_factory(server), options, clock=SystemClock())
    return OrmTransport(connection, SERIALIZER, name="orders")


async def test_concurrent_workers_each_claim_a_different_message(
    server: AsyncEngine, options: OrmOptions
) -> None:
    sender = _transport(server, options)
    for order in ("o-1", "o-2"):
        _ = await sender.send(Envelope(OrderPlaced(order)))
    one = Connection(engine_factory(server), options)
    other = Connection(engine_factory(server), options)

    claimed = await asyncio.gather(one.get(), other.get())

    ids = {message.id for message in claimed if message is not None}
    assert len(ids) == 2


async def test_a_row_another_transaction_holds_is_skipped_not_waited_for(
    server: AsyncEngine, options: OrmOptions
) -> None:
    sender = _transport(server, options)
    _ = await sender.send(Envelope(OrderPlaced("o-1")))
    _ = await sender.send(Envelope(OrderPlaced("o-2")))
    table = options.table_name

    async with server.connect() as holder:
        transaction = await holder.begin()
        _ = await holder.execute(text(f'SELECT id FROM "{table}" ORDER BY id LIMIT 1 FOR UPDATE'))
        claimed = await asyncio.wait_for(Connection(engine_factory(server), options).get(), 5)
        await transaction.rollback()

    assert claimed is not None
    assert claimed.body == '{"order":"o-2"}'


async def test_a_waiting_worker_is_woken_the_moment_a_message_is_sent(
    server: AsyncEngine, options: OrmOptions
) -> None:
    worker = _transport(server, options)
    await worker.setup()
    receiving = asyncio.ensure_future(anext(worker.get()))
    await asyncio.sleep(0.5)

    _ = await _transport(server, options).send(Envelope(OrderPlaced("o-1")))
    received = await asyncio.wait_for(receiving, 5)

    assert received.message == OrderPlaced("o-1")
    await worker.close()


async def test_a_transactional_send_wakes_the_worker_once_the_unit_commits(
    server: AsyncEngine, options: OrmOptions
) -> None:
    worker = _transport(server, options)
    await worker.setup()
    receiving = asyncio.ensure_future(anext(worker.get()))
    await asyncio.sleep(0.5)
    sessions = async_sessionmaker(server)

    async with sessions() as session:

        async def unit_session() -> AsyncSession:
            return session

        sender = OrmTransport(
            Connection(
                engine_factory(server),
                OrmOptions(table_name=options.table_name, transactional=True, auto_setup=False),
                session_factory=unit_session,
            ),
            SERIALIZER,
            name="orders",
        )
        _ = await sender.send(Envelope(OrderPlaced("o-1")))
        await asyncio.sleep(0.5)
        assert not receiving.done()
        await session.commit()

    received = await asyncio.wait_for(receiving, 5)

    assert received.message == OrderPlaced("o-1")
    await worker.close()
