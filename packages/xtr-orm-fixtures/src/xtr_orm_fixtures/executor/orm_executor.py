"""Loading fixtures in one transaction."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, final, override

from .abstract_executor import AbstractExecutor

if TYPE_CHECKING:
    from collections.abc import Iterable

    from xtr_orm_fixtures.fixture_interface import FixtureInterface

__all__ = ["OrmExecutor"]


@final
class OrmExecutor(AbstractExecutor):
    """Empties the database and loads every fixture in one transaction.

    A fixture that fails takes the emptying and every fixture before it back
    with it. On a session already in a transaction, the run takes a savepoint
    instead and leaves the transaction open: whoever began it commits it.
    """

    __slots__: ClassVar[tuple[str, ...]] = ()

    @override
    async def execute(self, fixtures: Iterable[FixtureInterface], *, append: bool = False) -> None:
        session = self._session
        transaction = session.begin_nested() if session.in_transaction() else session.begin()
        async with transaction:
            if not append:
                await self.purge()
            for fixture in fixtures:
                await self.load(fixture)
