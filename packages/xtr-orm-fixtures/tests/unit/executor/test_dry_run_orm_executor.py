"""Unit tests for :class:`xtr_orm_fixtures.executor.DryRunOrmExecutor`."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from tests.support.models import Base, Group, User
from tests.support.seeds import (
    DuplicateGroupFixture,
    GroupFixture,
    UserFixture,
    create_database,
    names,
)
from xtr_orm_fixtures.executor import DryRunOrmExecutor
from xtr_orm_fixtures.purger import OrmPurger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

pytestmark = pytest.mark.anyio


async def test_dry_run_leaves_the_database_unchanged(engine: AsyncEngine) -> None:
    await create_database(engine)

    async with AsyncSession(engine) as session:
        executor = DryRunOrmExecutor(session, OrmPurger(Base.metadata))
        await executor.execute([GroupFixture(), UserFixture()])

    assert (await names(engine, Group), await names(engine, User)) == (["old"], [])


async def test_dry_run_surfaces_constraint_errors(engine: AsyncEngine) -> None:
    await create_database(engine)

    async with AsyncSession(engine) as session:
        executor = DryRunOrmExecutor(session, OrmPurger(Base.metadata))
        with pytest.raises(IntegrityError):
            await executor.execute([DuplicateGroupFixture()], append=True)

    assert await names(engine, Group) == ["old"]


async def test_dry_run_in_a_transaction_rolls_back_only_its_savepoint(
    engine: AsyncEngine,
) -> None:
    await create_database(engine)

    async with AsyncSession(engine) as session:
        outer = await session.begin()
        session.add(Group(name="kept"))
        await session.flush()
        await DryRunOrmExecutor(session).execute([GroupFixture()], append=True)

        assert outer.is_active
        await outer.commit()

    assert await names(engine, Group) == ["old", "kept"]
