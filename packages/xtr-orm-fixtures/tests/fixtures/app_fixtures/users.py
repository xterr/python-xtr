"""A base no fixture is, and two fixtures built on it."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, override

from xtr_orm_fixtures import Fixture

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class NamedFixture(Fixture, ABC):
    """Abstract: a fixture only once it says its name."""

    @abstractmethod
    def name(self) -> str: ...

    @override
    async def load(self, session: AsyncSession) -> None:
        del session


class UserFixtures(NamedFixture):
    @override
    def name(self) -> str:
        return "users"


class AdminFixtures(NamedFixture):
    @override
    def name(self) -> str:
        return "admins"


class NotAFixture:
    pass
