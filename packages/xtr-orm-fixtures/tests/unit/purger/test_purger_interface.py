"""Unit tests for :class:`xtr_orm_fixtures.purger.PurgerInterface`."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import MetaData

from xtr_orm_fixtures.purger import OrmPurger, PurgerInterface

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class _Purger:
    async def purge(self, session: AsyncSession) -> None:
        del session


def test_a_class_with_purge_is_a_purger() -> None:
    assert isinstance(_Purger(), PurgerInterface)
    assert isinstance(OrmPurger(MetaData()), PurgerInterface)


def test_a_class_without_purge_is_not_a_purger() -> None:
    assert not isinstance(object(), PurgerInterface)
