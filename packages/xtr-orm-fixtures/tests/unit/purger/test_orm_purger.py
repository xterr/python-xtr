"""Unit tests for :class:`xtr_orm_fixtures.purger.OrmPurger`, on SQLite."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from sqlalchemy import Column, Integer, MetaData, Table, event, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.support.models import Base, Group, Tag, User
from xtr_orm_fixtures.purger import OrmPurger, PurgeMode

if TYPE_CHECKING:
    from sqlalchemy.engine.interfaces import DBAPIConnection
    from sqlalchemy.ext.asyncio import AsyncEngine
    from sqlalchemy.pool import ConnectionPoolEntry

pytestmark = pytest.mark.anyio


def _enforce_foreign_keys(connection: DBAPIConnection, record: ConnectionPoolEntry) -> None:
    del record
    cursor = connection.cursor()
    cursor.execute("PRAGMA foreign_keys = ON")
    cursor.close()


@pytest.fixture
async def seeded(engine: AsyncEngine) -> AsyncEngine:
    # SQLite checks foreign keys only when told to: told, a parent emptied first fails the purge.
    event.listen(engine.sync_engine, "connect", _enforce_foreign_keys)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with AsyncSession(engine) as session:
        group = Group(name="staff")
        session.add(User(name="ada", tags=[Tag(label="admin")], group_id=None))
        session.add(group)
        await session.flush()
        session.add(User(name="bob", group_id=group.id))
        await session.commit()
    return engine


async def _counts(engine: AsyncEngine) -> dict[str, int]:
    async with engine.connect() as connection:
        return {
            table.name: (
                await connection.execute(select(func.count()).select_from(table))
            ).scalar_one()
            for table in Base.metadata.sorted_tables
        }


async def _purge(engine: AsyncEngine, purger: OrmPurger) -> None:
    async with AsyncSession(engine) as session:
        await purger.purge(session)
        await session.commit()


def test_tables_come_children_first() -> None:
    names = [table.name for table in OrmPurger(Base.metadata).tables()]

    assert names.index("user_tags") < names.index("users") < names.index("groups")
    assert names.index("user_tags") < names.index("tags")


async def test_children_are_deleted_before_parents(seeded: AsyncEngine) -> None:
    await _purge(seeded, OrmPurger(Base.metadata))

    assert await _counts(seeded) == {"groups": 0, "tags": 0, "users": 0, "user_tags": 0}


async def test_association_tables_are_emptied(seeded: AsyncEngine) -> None:
    await _purge(seeded, OrmPurger(Base.metadata, excluded=["tags"]))

    counts = await _counts(seeded)
    assert (counts["user_tags"], counts["tags"]) == (0, 1)


async def test_excluded_tables_keep_their_rows(seeded: AsyncEngine) -> None:
    await _purge(seeded, OrmPurger(Base.metadata, excluded=["groups", "tags"]))

    assert await _counts(seeded) == {"groups": 1, "tags": 1, "users": 0, "user_tags": 0}


def test_a_table_is_excluded_by_its_schema_qualified_name() -> None:
    metadata = MetaData()
    _ = Table("events", metadata, Column("id", Integer, primary_key=True), schema="audit")
    _ = Table("users", metadata, Column("id", Integer, primary_key=True))

    tables = OrmPurger(metadata, excluded=["audit.events"]).tables()

    assert [table.fullname for table in tables] == ["users"]


def test_every_set_of_definitions_is_emptied() -> None:
    other = MetaData()
    _ = Table("audit", other, Column("id", Integer, primary_key=True))

    tables = OrmPurger([Base.metadata, other]).tables()

    assert [table.name for table in tables][-1] == "audit"
    assert len(tables) == len(Base.metadata.tables) + 1


async def test_truncate_falls_back_to_delete_on_sqlite(seeded: AsyncEngine) -> None:
    await _purge(seeded, OrmPurger(Base.metadata, mode=PurgeMode.TRUNCATE))

    assert set((await _counts(seeded)).values()) == {0}


async def test_purge_does_not_commit(seeded: AsyncEngine) -> None:
    async with AsyncSession(seeded) as session:
        await OrmPurger(Base.metadata).purge(session)
        await session.rollback()

    assert await _counts(seeded) == {"groups": 1, "tags": 1, "users": 2, "user_tags": 1}


async def test_nothing_to_empty_leaves_the_session_untouched(engine: AsyncEngine) -> None:
    async with AsyncSession(engine) as session:
        await OrmPurger(MetaData()).purge(session)

        assert not session.in_transaction()
