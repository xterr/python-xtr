"""The store on a real PostgreSQL server: a delete racing a fork.

Skipped unless ``XTR_TEST_POSTGRES_URL`` names a database to run on, as an
asyncpg URL — ``postgresql+asyncpg://user:password@localhost/test``. Every test
uses tables of its own and drops them, so the database can be shared.
"""

from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from pydantic_ai import Agent
from pydantic_ai.conversation import Conversation
from pydantic_ai.conversation_store import ConversationConflict
from pydantic_ai.models.test import TestModel
from sqlalchemy import MetaData, delete, func, insert, select
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from xtr_ai_orm_conversation_store import ConversationTables, OrmConversationStore

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

pytestmark = [
    pytest.mark.anyio,
    pytest.mark.skipif(
        "XTR_TEST_POSTGRES_URL" not in os.environ,
        reason="XTR_TEST_POSTGRES_URL names no PostgreSQL database to run on",
    ),
]

#: Long enough for the racing statement to reach its lock and wait on it.
_SETTLE = 0.3


@pytest.fixture
def tables() -> ConversationTables:
    return ConversationTables.define(MetaData(), f"t{uuid4().hex[:12]}_")


@pytest.fixture
async def engine(tables: ConversationTables) -> AsyncIterator[AsyncEngine]:
    built = create_async_engine(os.environ["XTR_TEST_POSTGRES_URL"])
    metadata = tables.conversation.metadata
    async with built.begin() as connection:
        await connection.run_sync(metadata.create_all)
    try:
        yield built
    finally:
        async with built.begin() as connection:
            await connection.run_sync(metadata.drop_all)
        await built.dispose()


@pytest.fixture
def store(engine: AsyncEngine, tables: ConversationTables) -> OrmConversationStore:
    prefix = tables.conversation.name.removesuffix("conversation")
    return OrmConversationStore(engine, table_prefix=prefix)


async def _started(store: OrmConversationStore, conversation_id: str) -> None:
    result = await Agent(TestModel(custom_output_text="ok")).run(
        "one", conversation=Conversation(conversation_id=conversation_id)
    )
    _ = await store.save(result)


async def _entries(engine: AsyncEngine, tables: ConversationTables) -> int:
    async with engine.connect() as connection:
        return int(await connection.scalar(select(func.count()).select_from(tables.entry)) or 0)


async def test_deleting_a_conversation_keeps_entries_a_concurrent_fork_reaches(
    store: OrmConversationStore, engine: AsyncEngine, tables: ConversationTables
) -> None:
    await _started(store, "c1")
    origin = await store.read_record("c1")
    assert origin is not None
    conversation = tables.conversation

    async with engine.connect() as forking:
        transaction = await forking.begin()
        # What a fork's write holds until it commits: a share lock on its origin, and its own row.
        _ = await forking.execute(
            select(conversation.c.conversation_id)
            .where(conversation.c.conversation_id == "c1")
            .with_for_update(read=True)
        )
        row = (
            (
                await forking.execute(
                    select(conversation).where(conversation.c.conversation_id == "c1")
                )
            )
            .mappings()
            .one()
        )
        fork_row = {
            **dict(row),
            "conversation_id": "f1",
            "forked_from": "c1",
            "forked_at": origin.head_id,
            "revision": uuid4().hex,
        }
        _ = await forking.execute(insert(conversation).values(fork_row))
        deleting = asyncio.ensure_future(store.delete("c1"))
        await asyncio.sleep(_SETTLE)
        await transaction.commit()

    await asyncio.wait_for(deleting, 10)

    kept = await store.load("f1")
    assert kept is not None
    assert len(kept.messages) == 2
    assert await _entries(engine, tables) == 2


async def test_a_fork_of_a_conversation_being_deleted_conflicts(
    store: OrmConversationStore, engine: AsyncEngine, tables: ConversationTables
) -> None:
    await _started(store, "c1")
    conversation = tables.conversation

    async with engine.connect() as deleting:
        transaction = await deleting.begin()
        _ = await deleting.execute(
            delete(conversation).where(conversation.c.conversation_id == "c1")
        )
        forking = asyncio.ensure_future(store.fork("c1", new_conversation_id="f1"))
        await asyncio.sleep(_SETTLE)
        await transaction.commit()

    with pytest.raises(ConversationConflict):
        _ = await asyncio.wait_for(forking, 10)
    assert await store.read_record("f1") is None
