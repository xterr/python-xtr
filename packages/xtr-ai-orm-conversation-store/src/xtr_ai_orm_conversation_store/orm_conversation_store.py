"""A pydantic-ai conversation store on two database tables."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from pydantic_ai.conversation_store import ConversationConflict, ConversationStore
from sqlalchemy import MetaData, delete, func, insert, literal, or_, select, update
from sqlalchemy.exc import IntegrityError
from typing_extensions import override

from ._rows import entry_from_row, entry_row, record_from_row, record_row
from .conversation_tables import DEFAULT_TABLE_PREFIX, ConversationTables

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from pydantic_ai.conversation_store import ConversationEntry, ConversationRecord
    from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

__all__ = ["OrmConversationStore"]


@final
class OrmConversationStore(ConversationStore):
    """Conversations in ``{prefix}conversation`` and ``{prefix}conversation_entry``.

    Every call runs in a short transaction of its own on ``engine`` — give it
    the primary's — and commits before it returns: a conversation is never
    part of the caller's unit of work, so a long model call holds no database
    connection, and a rollback of the caller's work never takes a saved turn
    with it. Saving a record and the messages it adds is one transaction, so a
    conflict leaves neither behind.

    A conversation's history is read with one recursive query. Deleting a
    conversation deletes every message only it reaches; the messages a fork of
    it — or the conversation it was forked from — still reaches stay until
    the last of them is deleted.

    ```python
    store = OrmConversationStore(engine)
    conversation = await store.load(conversation_id) or Conversation(
        conversation_id=conversation_id
    )
    result = await agent.run(prompt, conversation=conversation)
    await store.save(result)
    ```
    """

    def __init__(self, engine: AsyncEngine, *, table_prefix: str = DEFAULT_TABLE_PREFIX) -> None:
        """Store through ``engine``, in tables whose names start with ``table_prefix``."""
        self._engine = engine
        self._tables = ConversationTables.define(MetaData(), table_prefix)

    @override
    async def read_record(self, conversation_id: str) -> ConversationRecord | None:
        conversation = self._tables.conversation
        async with self._engine.connect() as connection:
            row = (
                await connection.execute(
                    select(conversation).where(conversation.c.conversation_id == conversation_id)
                )
            ).first()
        return record_from_row(row) if row is not None else None

    @override
    async def read_records(
        self, *, scope: str | None = None, limit: int | None = None
    ) -> Sequence[ConversationRecord]:
        conversation = self._tables.conversation
        query = select(conversation).order_by(
            conversation.c.updated_at.desc(), conversation.c.conversation_id
        )
        if scope is not None:
            query = query.where(conversation.c.scope == scope)
        if limit is not None:
            query = query.limit(limit)
        async with self._engine.connect() as connection:
            rows = (await connection.execute(query)).all()
        return [record_from_row(row) for row in rows]

    @override
    async def write_record(
        self,
        record: ConversationRecord,
        *,
        new_entries: Sequence[ConversationEntry] = (),
        expected_revision: str | None,
    ) -> None:
        conversation = self._tables.conversation
        async with self._engine.begin() as connection:
            if expected_revision is None:
                try:
                    _ = await connection.execute(insert(conversation).values(record_row(record)))
                except IntegrityError:
                    raise ConversationConflict(record.conversation_id) from None
            else:
                result = await connection.execute(
                    update(conversation)
                    .where(
                        conversation.c.conversation_id == record.conversation_id,
                        conversation.c.revision == expected_revision,
                    )
                    .values(record_row(record))
                )
                if result.rowcount != 1:
                    raise ConversationConflict(record.conversation_id)
            if new_entries:
                _ = await connection.execute(
                    insert(self._tables.entry), [entry_row(entry) for entry in new_entries]
                )
            head = record.head_id
            new_ids = {entry.id for entry in new_entries}
            if (
                head is not None
                and head not in new_ids
                and not await self._has_entry(connection, head)
            ):
                raise ConversationConflict(record.conversation_id)

    @override
    async def delete_record(self, conversation_id: str, *, expected_revision: str) -> None:
        conversation = self._tables.conversation
        async with self._engine.begin() as connection:
            family = await self._fork_family(connection, conversation_id)
            deleted = await connection.execute(
                delete(conversation).where(
                    conversation.c.conversation_id == conversation_id,
                    conversation.c.revision == expected_revision,
                )
            )
            if deleted.rowcount != 1:
                raise ConversationConflict(conversation_id)
            own = family.pop(conversation_id)
            reached = await self._reachable(connection, own)
            kept = await self._reachable(
                connection, [tip for tips in family.values() for tip in tips]
            )
            released = sorted(reached - kept)
            if released:
                entry = self._tables.entry
                _ = await connection.execute(delete(entry).where(entry.c.id.in_(released)))

    @override
    async def read_entry(self, entry_id: str) -> ConversationEntry:
        entry = self._tables.entry
        async with self._engine.connect() as connection:
            row = (await connection.execute(select(entry).where(entry.c.id == entry_id))).first()
        if row is None:
            raise KeyError(entry_id)
        return entry_from_row(row)

    @override
    async def read_history(
        self, head_id: str | None, *, limit: int | None = None
    ) -> list[ConversationEntry]:
        """Read the history up to ``head_id`` in one recursive query.

        Raises:
            KeyError: When an entry of the history is missing, as a concurrent
                delete leaves it.
        """
        if head_id is None or limit == 0:
            return []
        entry = self._tables.entry
        walk = (select(entry, literal(1).label("depth")).where(entry.c.id == head_id)).cte(
            "history", recursive=True
        )
        step = select(entry, (walk.c.depth + 1).label("depth")).join(
            walk, entry.c.id == walk.c.parent_id
        )
        if limit is not None:
            step = step.where(walk.c.depth < limit)
        walk = walk.union_all(step)
        async with self._engine.connect() as connection:
            rows = (await connection.execute(select(walk).order_by(walk.c.depth.desc()))).all()
        if not rows:
            raise KeyError(head_id)
        reached_limit = limit is not None and len(rows) >= limit
        if rows[0].parent_id is not None and not reached_limit:
            raise KeyError(rows[0].parent_id)
        return [entry_from_row(row) for row in rows]

    async def _has_entry(self, connection: AsyncConnection, entry_id: str) -> bool:
        entry = self._tables.entry
        found = await connection.scalar(
            select(func.count()).select_from(entry).where(entry.c.id == entry_id)
        )
        return bool(found)

    async def _fork_family(
        self, connection: AsyncConnection, conversation_id: str
    ) -> dict[str, list[str]]:
        """Every conversation sharing entries with ``conversation_id``, with its histories' tips.

        Entries are shared only by forking, so the family is everything linked
        to the conversation by ``forked_from``, in either direction.
        """
        conversation = self._tables.conversation
        family: dict[str, list[str]] = {}
        explored: set[str] = set()
        pending: set[str] = {conversation_id}
        while pending:
            rows = (
                await connection.execute(
                    select(conversation).where(
                        or_(
                            conversation.c.conversation_id.in_(pending),
                            conversation.c.forked_from.in_(pending),
                        )
                    )
                )
            ).all()
            explored |= pending
            pending = set()
            for row in rows:
                record = record_from_row(row)
                family[record.conversation_id] = _tips(record)
                pending.add(record.conversation_id)
                if record.forked_from is not None:
                    pending.add(record.forked_from)
            pending -= explored
        return family

    async def _reachable(self, connection: AsyncConnection, tips: Iterable[str]) -> set[str]:
        """Every entry on the histories ending at ``tips``."""
        starts = sorted(set(tips))
        if not starts:
            return set()
        entry = self._tables.entry
        walk = (select(entry.c.id, entry.c.parent_id).where(entry.c.id.in_(starts))).cte(
            "reached", recursive=True
        )
        walk = walk.union(
            select(entry.c.id, entry.c.parent_id).join(walk, entry.c.id == walk.c.parent_id)
        )
        rows = (await connection.execute(select(walk.c.id))).all()
        return {row.id for row in rows}


def _tips(record: ConversationRecord) -> list[str]:
    """Where ``record``'s histories end: its head, the branches it left, and where it was forked."""
    return [tip for tip in (record.head_id, *record.branches, record.forked_at) if tip is not None]
