"""Fixtures the executor tests load, and the database they load into."""

from __future__ import annotations

from typing import TYPE_CHECKING, final, override

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.support.models import Base, Group, User
from xtr_orm_fixtures import DependentFixtureInterface, Fixture, OrderedFixtureInterface

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy.ext.asyncio import AsyncEngine

    from xtr_orm_fixtures import FixtureInterface

__all__ = [
    "BrokenFixture",
    "DuplicateGroupFixture",
    "GroupFixture",
    "NumberedFixture",
    "UserFixture",
    "create_database",
    "names",
]


@final
class GroupFixture(Fixture):
    """Adds the ``staff`` group, shared as the reference ``staff``."""

    @override
    async def load(self, session: AsyncSession) -> None:
        group = Group(name="staff")
        session.add(group)
        self.add_reference("staff", group)


@final
class UserFixture(Fixture, DependentFixtureInterface):
    """Adds ``ada`` to the group :class:`GroupFixture` shared."""

    @override
    def get_dependencies(self) -> Sequence[type[FixtureInterface]]:
        return (GroupFixture,)

    @override
    async def load(self, session: AsyncSession) -> None:
        group = self.get_reference("staff", Group)
        session.add(User(name="ada", group_id=group.id))


@final
class NumberedFixture(Fixture, OrderedFixtureInterface):
    @override
    def get_order(self) -> int:
        return 3

    @override
    async def load(self, session: AsyncSession) -> None:
        del session


@final
class BrokenFixture(Fixture):
    """Adds a group, then fails."""

    @override
    async def load(self, session: AsyncSession) -> None:
        session.add(Group(name="half-done"))
        await session.flush()
        raise RuntimeError("the fixture broke")


@final
class DuplicateGroupFixture(Fixture):
    """Adds a group under a key the database already holds."""

    @override
    async def load(self, session: AsyncSession) -> None:
        session.add(Group(id=1, name="twin"))


async def create_database(engine: AsyncEngine) -> None:
    """Create the tables, holding one group, ``old``, under key 1."""
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with AsyncSession(engine) as session:
        session.add(Group(id=1, name="old"))
        await session.commit()


async def names(engine: AsyncEngine, model: type[Group | User]) -> list[str]:
    """Return the names the table of ``model`` holds, in key order."""
    async with AsyncSession(engine) as session:
        return list(await session.scalars(select(model.name).order_by(model.id)))
