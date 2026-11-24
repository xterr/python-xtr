"""Emptying with ``TRUNCATE`` on a real PostgreSQL server.

Skipped unless ``ORM_FIXTURES_POSTGRES_URL`` names a database to run on, as an
asyncpg URL — ``postgresql+asyncpg://user:password@localhost/test``. Every test
uses tables of its own and drops them, so the database can be shared.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from sqlalchemy import Column, ForeignKey, Integer, MetaData, Table, func, insert, select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from xtr_orm_fixtures.purger import OrmPurger, PurgeMode

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from sqlalchemy.ext.asyncio import AsyncEngine

pytestmark = [
    pytest.mark.anyio,
    pytest.mark.skipif(
        "ORM_FIXTURES_POSTGRES_URL" not in os.environ,
        reason="set ORM_FIXTURES_POSTGRES_URL to run",
    ),
]


@pytest.fixture
def metadata() -> MetaData:
    prefix = f"fx_{uuid4().hex[:10]}"
    built = MetaData()
    _ = Table(f"{prefix}_parents", built, Column("id", Integer, primary_key=True))
    for name in ("children", "kept"):
        _ = Table(
            f"{prefix}_{name}",
            built,
            Column("id", Integer, primary_key=True),
            Column("parent_id", Integer, ForeignKey(f"{prefix}_parents.id")),
        )
    return built


@pytest.fixture
async def server(metadata: MetaData) -> AsyncIterator[AsyncEngine]:
    built = create_async_engine(os.environ["ORM_FIXTURES_POSTGRES_URL"])
    async with built.begin() as connection:
        await connection.run_sync(metadata.create_all)
        parents, children, kept = metadata.sorted_tables
        _ = await connection.execute(insert(parents).values(id=1))
        _ = await connection.execute(insert(children).values(id=1, parent_id=1))
        _ = await connection.execute(insert(kept).values(id=1, parent_id=1))
    yield built
    async with built.begin() as connection:
        await connection.run_sync(metadata.drop_all)
    await built.dispose()


async def test_truncate_empties_related_tables(server: AsyncEngine, metadata: MetaData) -> None:
    async with AsyncSession(server) as session:
        await OrmPurger(metadata, mode=PurgeMode.TRUNCATE).purge(session)
        await session.commit()

    async with server.connect() as connection:
        for table in metadata.sorted_tables:
            count = await connection.execute(select(func.count()).select_from(table))
            assert count.scalar_one() == 0


async def test_truncate_refuses_when_an_excluded_table_references_a_purged_one(
    server: AsyncEngine, metadata: MetaData
) -> None:
    kept = metadata.sorted_tables[-1]
    purger = OrmPurger(metadata, excluded=[kept.name], mode=PurgeMode.TRUNCATE)

    async with AsyncSession(server) as session:
        with pytest.raises(DBAPIError, match="referenced in a foreign key constraint"):
            await purger.purge(session)
