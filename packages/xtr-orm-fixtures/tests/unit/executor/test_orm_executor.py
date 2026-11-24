"""Unit tests for :class:`xtr_orm_fixtures.executor.OrmExecutor`."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from tests.support.models import Base, Group, User
from tests.support.seeds import BrokenFixture, GroupFixture, UserFixture, create_database, names
from xtr_orm_fixtures.executor import OrmExecutor
from xtr_orm_fixtures.purger import OrmPurger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

pytestmark = pytest.mark.anyio


async def test_purges_then_loads_in_order(engine: AsyncEngine) -> None:
    await create_database(engine)

    async with AsyncSession(engine) as session:
        await OrmExecutor(session, OrmPurger(Base.metadata)).execute(
            [GroupFixture(), UserFixture()]
        )

    assert (await names(engine, Group), await names(engine, User)) == (["staff"], ["ada"])


async def test_append_keeps_existing_rows(engine: AsyncEngine) -> None:
    await create_database(engine)

    async with AsyncSession(engine) as session:
        await OrmExecutor(session, OrmPurger(Base.metadata)).execute([GroupFixture()], append=True)

    assert await names(engine, Group) == ["old", "staff"]


async def test_failure_rolls_back_purge_and_loads(engine: AsyncEngine) -> None:
    await create_database(engine)

    async with AsyncSession(engine) as session:
        executor = OrmExecutor(session, OrmPurger(Base.metadata))
        with pytest.raises(RuntimeError, match="the fixture broke"):
            await executor.execute([GroupFixture(), BrokenFixture()])

    assert await names(engine, Group) == ["old"]


async def test_references_flow_between_fixtures(engine: AsyncEngine) -> None:
    await create_database(engine)

    async with AsyncSession(engine) as session:
        executor = OrmExecutor(session, OrmPurger(Base.metadata))
        await executor.execute([GroupFixture(), UserFixture()])

        # The reference is the object the session tracks, not a copy.
        assert executor.references.get_reference("staff", Group) in session

    async with AsyncSession(engine) as session:
        ada = await session.get_one(User, 1)
        assert ada.group_id is not None
        assert (await session.get_one(Group, ada.group_id)).name == "staff"


async def test_existing_transaction_gets_a_savepoint_and_is_not_committed(
    engine: AsyncEngine,
) -> None:
    await create_database(engine)

    async with AsyncSession(engine) as session:
        outer = await session.begin()
        await OrmExecutor(session, OrmPurger(Base.metadata)).execute([GroupFixture()])

        assert outer.is_active
        assert session.in_transaction()
        await outer.rollback()

    assert await names(engine, Group) == ["old"]
