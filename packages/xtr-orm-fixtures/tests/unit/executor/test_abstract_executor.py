"""Unit tests for :class:`xtr_orm_fixtures.executor.AbstractExecutor`."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from tests.support.models import Base, Group
from tests.support.recording_logger import RecordingLogger
from tests.support.seeds import GroupFixture, NumberedFixture, create_database, names
from xtr_orm_fixtures.exception import InvalidArgumentError
from xtr_orm_fixtures.executor import OrmExecutor
from xtr_orm_fixtures.purger import OrmPurger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

pytestmark = pytest.mark.anyio


@final
class _Unshared:
    """A fixture with ``load`` alone: it shares no references."""

    def __init__(self) -> None:
        self.loaded = False

    async def load(self, session: AsyncSession) -> None:
        session.add(Group(name="unshared"))
        self.loaded = True


async def test_purge_without_purger_raises(engine: AsyncEngine) -> None:
    async with AsyncSession(engine) as session:
        executor = OrmExecutor(session)

        with pytest.raises(InvalidArgumentError) as caught:
            await executor.purge()

    assert caught.value.reason == (
        "OrmExecutor has no purger to empty the database with; give it one, or load in append mode"
    )


async def test_logs_purging_and_each_fixture(engine: AsyncEngine) -> None:
    await create_database(engine)
    logger = RecordingLogger()

    async with AsyncSession(engine) as session:
        executor = OrmExecutor(session, OrmPurger(Base.metadata), logger)
        await executor.execute([NumberedFixture(), GroupFixture()])

    assert logger.records == [
        ("info", "purging database", {}),
        (
            "info",
            "loading [{order}] {fixture}",
            {"fixture": "tests.support.seeds.NumberedFixture", "order": 3},
        ),
        (
            "info",
            "loading {fixture}",
            {"fixture": "tests.support.seeds.GroupFixture"},
        ),
    ]


async def test_load_hands_over_the_references_and_flushes(engine: AsyncEngine) -> None:
    await create_database(engine)

    async with AsyncSession(engine) as session, session.begin():
        executor = OrmExecutor(session)
        await executor.load(GroupFixture())

        staff = executor.references.get_reference("staff", Group)
        assert staff.id is not None
        assert staff in session


async def test_a_logger_is_optional(engine: AsyncEngine) -> None:
    await create_database(engine)

    async with AsyncSession(engine) as session:
        await OrmExecutor(session).execute([GroupFixture()], append=True)

    assert await names(engine, Group) == ["old", "staff"]


async def test_a_fixture_sharing_nothing_is_loaded_without_references(
    engine: AsyncEngine,
) -> None:
    await create_database(engine)
    fixture = _Unshared()

    async with AsyncSession(engine) as session:
        await OrmExecutor(session).execute([fixture], append=True)

    assert fixture.loaded
    assert await names(engine, Group) == ["old", "unshared"]
