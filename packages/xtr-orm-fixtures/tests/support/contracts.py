"""Plain classes each keeping one fixture contract, for the contracts' tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy.ext.asyncio import AsyncSession

    from xtr_orm_fixtures import FixtureInterface, ReferenceRepository

__all__ = ["Dependent", "Grouped", "NoLoad", "Ordered", "Plain", "Shared"]


class Plain:
    async def load(self, session: AsyncSession) -> None:
        del session


class Shared(Plain):
    def set_reference_repository(self, repository: ReferenceRepository) -> None:
        del repository


class Dependent(Plain):
    def get_dependencies(self) -> Sequence[type[FixtureInterface]]:
        return (Plain,)


class Ordered(Plain):
    def get_order(self) -> int:
        return 1


class Grouped(Plain):
    @classmethod
    def get_groups(cls) -> Sequence[str]:
        return ("demo",)


class NoLoad:
    """Every method but ``load``: no fixture at all."""

    def set_reference_repository(self, repository: ReferenceRepository) -> None:
        del repository

    def get_dependencies(self) -> Sequence[type[FixtureInterface]]:
        return (Plain,)

    def get_order(self) -> int:
        return 1

    @classmethod
    def get_groups(cls) -> Sequence[str]:
        return ("demo",)
