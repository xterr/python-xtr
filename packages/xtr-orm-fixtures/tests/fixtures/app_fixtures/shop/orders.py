"""A fixture depending on one it imports from another module."""

from __future__ import annotations

from typing import TYPE_CHECKING, override

from tests.fixtures.app_fixtures.users import UserFixtures
from xtr_orm_fixtures import DependentFixtureInterface, Fixture

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy.ext.asyncio import AsyncSession

    from xtr_orm_fixtures import FixtureInterface

__all__ = ["OrderFixtures", "UserFixtures"]


class OrderFixtures(Fixture, DependentFixtureInterface):
    @override
    def get_dependencies(self) -> Sequence[type[FixtureInterface]]:
        return (UserFixtures,)

    @override
    async def load(self, session: AsyncSession) -> None:
        del session
