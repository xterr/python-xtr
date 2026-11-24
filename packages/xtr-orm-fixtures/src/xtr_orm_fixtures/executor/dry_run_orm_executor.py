"""Loading fixtures only to see that they load."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, final, override

from .abstract_executor import AbstractExecutor

if TYPE_CHECKING:
    from collections.abc import Iterable

    from xtr_orm_fixtures.fixture_interface import FixtureInterface

__all__ = ["DryRunOrmExecutor"]


@final
class DryRunOrmExecutor(AbstractExecutor):
    """Runs the emptying and every fixture as :class:`OrmExecutor` does, then rolls it all back.

    The statements reach the database, so a constraint a fixture breaks fails
    the run as it would for real, yet nothing stays. On a session already in a
    transaction, only the savepoint the run took is rolled back.
    """

    __slots__: ClassVar[tuple[str, ...]] = ()

    @override
    async def execute(self, fixtures: Iterable[FixtureInterface], *, append: bool = False) -> None:
        session = self._session
        transaction = await (
            session.begin_nested() if session.in_transaction() else session.begin()
        )
        try:
            if not append:
                await self.purge()
            for fixture in fixtures:
                await self.load(fixture)
        finally:
            await transaction.rollback()
