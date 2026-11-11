from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from pydantic_ai import Agent
from pydantic_ai.conversation import Conversation
from pydantic_ai.conversation_store import ConversationConflict, ConversationRecord
from pydantic_ai.messages import BinaryContent, ModelRequest, UserPromptPart
from pydantic_ai.models.test import TestModel
from sqlalchemy import MetaData, delete, func, select
from sqlalchemy.pool import QueuePool

from xtr_ai_orm_conversation_store import ConversationTables

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

    from xtr_ai_orm_conversation_store import OrmConversationStore

pytestmark = pytest.mark.anyio


def _agent() -> Agent[None, str]:
    return Agent(TestModel(custom_output_text="ok"))


async def _turn(store: OrmConversationStore, conversation_id: str, prompt: str) -> None:
    conversation = await store.load(conversation_id) or Conversation(
        conversation_id=conversation_id
    )
    result = await _agent().run(prompt, conversation=conversation)
    _ = await store.save(result)


async def _entries(engine: AsyncEngine) -> int:
    entry = ConversationTables.define(MetaData()).entry
    async with engine.connect() as connection:
        return int(await connection.scalar(select(func.count()).select_from(entry)) or 0)


async def test_a_saved_conversation_loads_back(store: OrmConversationStore) -> None:
    await _turn(store, "c1", "hello")

    loaded = await store.load("c1")

    assert loaded is not None
    assert len(loaded.messages) == 2
    assert loaded.usage.requests == 1
    assert loaded.conversation_id == "c1"


async def test_a_conversation_grows_turn_by_turn_and_loads_its_tail(
    store: OrmConversationStore,
) -> None:
    await _turn(store, "c1", "one")
    await _turn(store, "c1", "two")

    whole = await store.load("c1")
    tail = await store.load("c1", limit=1)

    assert whole is not None
    assert tail is not None
    assert len(whole.messages) == 4
    assert tail.messages == whole.messages[-1:]


async def test_an_unknown_conversation_is_none(store: OrmConversationStore) -> None:
    assert await store.load("nope") is None


async def test_a_save_over_a_newer_revision_conflicts(store: OrmConversationStore) -> None:
    await _turn(store, "c1", "one")
    first = await store.load("c1")
    second = await store.load("c1")
    assert first is not None
    assert second is not None

    _ = await store.save(await _agent().run("a", conversation=first))

    with pytest.raises(ConversationConflict):
        _ = await store.save(await _agent().run("b", conversation=second))


async def test_creating_a_conversation_twice_conflicts(store: OrmConversationStore) -> None:
    await _turn(store, "c1", "one")
    record = await store.read_record("c1")
    assert record is not None

    with pytest.raises(ConversationConflict):
        await store.write_record(record, expected_revision=None)


async def test_a_record_pointing_at_a_missing_entry_conflicts(store: OrmConversationStore) -> None:
    with pytest.raises(ConversationConflict):
        await store.write_record(
            ConversationRecord(conversation_id="c1", head_id="gone"), expected_revision=None
        )

    assert await store.read_record("c1") is None


async def test_writing_over_a_revision_another_writer_replaced_conflicts(
    store: OrmConversationStore,
) -> None:
    await _turn(store, "c1", "one")
    record = await store.read_record("c1")
    assert record is not None

    # What a concurrent writer meets when it read the record before another one saved it.
    with pytest.raises(ConversationConflict):
        await store.write_record(record, expected_revision="a-revision-already-replaced")


async def test_deleting_a_revision_another_writer_replaced_conflicts(
    store: OrmConversationStore,
) -> None:
    await _turn(store, "c1", "one")

    with pytest.raises(ConversationConflict):
        await store.delete_record("c1", expected_revision="a-revision-already-replaced")

    assert await store.load("c1") is not None


async def test_an_entry_is_read_by_its_id(store: OrmConversationStore) -> None:
    await _turn(store, "c1", "one")
    record = await store.read_record("c1")
    assert record is not None
    assert record.head_id is not None

    entry = await store.read_entry(record.head_id)

    assert entry.id == record.head_id


async def test_an_empty_history_reads_nothing(store: OrmConversationStore) -> None:
    assert await store.read_history(None) == []
    assert await store.read_history("any", limit=0) == []


async def test_a_history_whose_head_is_missing_is_a_lookup_error(
    store: OrmConversationStore,
) -> None:
    with pytest.raises(KeyError):
        _ = await store.read_history("no-such-entry")


async def test_a_branch_keeps_the_history_it_leaves(store: OrmConversationStore) -> None:
    await _turn(store, "c1", "one")
    await _turn(store, "c1", "two")
    loaded = await store.load("c1")
    assert loaded is not None

    branched = await store.branch("c1", at=2, expected_revision=loaded.revision)
    _ = await store.save(await _agent().run("again", conversation=branched))

    record = await store.read_record("c1")
    reloaded = await store.load("c1")
    assert record is not None
    assert reloaded is not None
    assert len(record.branches) == 1
    assert len(reloaded.messages) == 4


async def test_deleting_a_conversation_deletes_its_messages(
    store: OrmConversationStore, engine: AsyncEngine
) -> None:
    await _turn(store, "c1", "one")
    await _turn(store, "c2", "other")

    await store.delete("c1")

    assert await store.load("c1") is None
    assert await _entries(engine) == 2


async def test_a_fork_keeps_what_it_shares_until_both_are_deleted(
    store: OrmConversationStore, engine: AsyncEngine
) -> None:
    await _turn(store, "c1", "one")
    fork = await store.fork("c1", new_conversation_id="f1")
    _ = await store.save(await _agent().run("branch off", conversation=fork))

    await store.delete("c1")

    kept = await store.load("f1")
    assert kept is not None
    assert len(kept.messages) == 4
    assert await _entries(engine) == 4

    await store.delete("f1")

    assert await _entries(engine) == 0


async def test_deleting_a_fork_keeps_its_origin(
    store: OrmConversationStore, engine: AsyncEngine
) -> None:
    await _turn(store, "c1", "one")
    fork = await store.fork("c1", new_conversation_id="f1")
    _ = await store.save(await _agent().run("branch off", conversation=fork))

    await store.delete("f1")

    origin = await store.load("c1")
    assert origin is not None
    assert len(origin.messages) == 2
    assert await _entries(engine) == 2


async def test_records_are_listed_newest_first_by_scope(store: OrmConversationStore) -> None:
    for conversation_id, scope in (("a", "u1"), ("b", "u2"), ("c", "u1")):
        conversation = Conversation(conversation_id=conversation_id)
        _ = await store.save(await _agent().run("hi", conversation=conversation), scope=scope)

    mine = await store.read_records(scope="u1")
    newest = await store.read_records(limit=1)

    assert [record.conversation_id for record in mine] == ["c", "a"]
    assert [record.conversation_id for record in newest] == ["c"]
    assert await store.load("a", scope="u2") is None


async def test_binary_content_survives_the_round_trip(store: OrmConversationStore) -> None:
    image = BinaryContent(data=b"\x89PNG\x00\xff", media_type="image/png")
    conversation = Conversation(
        conversation_id="c1",
        messages=[ModelRequest(parts=[UserPromptPart(["look", image])])],
    )
    _ = await store.save(conversation)

    loaded = await store.load("c1")

    assert loaded is not None
    part = loaded.messages[0].parts[0]
    assert isinstance(part, UserPromptPart)
    loaded_image = part.content[1]
    assert isinstance(loaded_image, BinaryContent)
    assert loaded_image.data == image.data
    assert loaded_image.media_type == "image/png"


async def test_a_history_missing_an_entry_is_a_lookup_error(
    store: OrmConversationStore, engine: AsyncEngine
) -> None:
    await _turn(store, "c1", "one")
    record = await store.read_record("c1")
    assert record is not None
    history = await store.read_history(record.head_id)
    entry = ConversationTables.define(MetaData()).entry
    async with engine.begin() as connection:
        _ = await connection.execute(delete(entry).where(entry.c.id == history[0].id))

    with pytest.raises(KeyError):
        _ = await store.read_history(record.head_id)
    with pytest.raises(KeyError):
        _ = await store.read_entry(history[0].id)


async def test_a_message_larger_than_a_plain_text_column_round_trips(
    store: OrmConversationStore,
) -> None:
    image = BinaryContent(data=bytes(range(256)) * 1024, media_type="image/png")  # 256 KB
    conversation = Conversation(
        conversation_id="c1",
        messages=[ModelRequest(parts=[UserPromptPart(["look", image])])],
    )
    _ = await store.save(conversation)

    loaded = await store.load("c1")

    assert loaded is not None
    part = loaded.messages[0].parts[0]
    assert isinstance(part, UserPromptPart)
    loaded_image = part.content[1]
    assert isinstance(loaded_image, BinaryContent)
    assert loaded_image.data == image.data


async def test_no_connection_is_held_between_calls(
    store: OrmConversationStore, engine: AsyncEngine
) -> None:
    await _turn(store, "c1", "one")
    _ = await store.load("c1")
    await store.delete("c1")

    pool = engine.pool
    assert isinstance(pool, QueuePool)
    assert pool.checkedout() == 0
