"""What every executor does: empty the database, then load fixtures one by one."""

from __future__ import annotations

from abc import ABCMeta, abstractmethod
from typing import TYPE_CHECKING, ClassVar

from xtr_logging_contracts import NullLogger

from xtr_orm_fixtures.exception import InvalidArgumentError
from xtr_orm_fixtures.ordered_fixture_interface import OrderedFixtureInterface
from xtr_orm_fixtures.reference_repository import ReferenceRepository
from xtr_orm_fixtures.shared_fixture_interface import SharedFixtureInterface

if TYPE_CHECKING:
    from collections.abc import Iterable

    from sqlalchemy.ext.asyncio import AsyncSession
    from xtr_logging_contracts import LoggerInterface

    from xtr_orm_fixtures.fixture_interface import FixtureInterface
    from xtr_orm_fixtures.purger import PurgerInterface

__all__ = ["AbstractExecutor"]


class AbstractExecutor(metaclass=ABCMeta):
    """Loads fixtures through one session, sharing one reference repository between them.

    Each fixture's objects are flushed once it is loaded, so the next fixture
    sees their keys, and the session is never cleared: a reference handed on
    stays the live object the session tracks. A subclass decides only what
    the run is wrapped in — see :meth:`execute`.
    """

    __slots__: ClassVar[tuple[str, ...]] = ("_logger", "_purger", "_references", "_session")

    def __init__(
        self,
        session: AsyncSession,
        purger: PurgerInterface | None = None,
        logger: LoggerInterface | None = None,
    ) -> None:
        """Load through ``session``, emptying with ``purger``, saying what happens to ``logger``."""
        self._session: AsyncSession = session
        self._purger: PurgerInterface | None = purger
        self._logger: LoggerInterface = logger if logger is not None else NullLogger()
        self._references: ReferenceRepository = ReferenceRepository()

    @property
    def references(self) -> ReferenceRepository:
        """The references the fixtures of this executor share."""
        return self._references

    async def purge(self) -> None:
        """Empty the database with the purger.

        Raises:
            InvalidArgumentError: If the executor was given no purger.
        """
        if self._purger is None:
            raise InvalidArgumentError(
                f"{type(self).__name__} has no purger to empty the database with; "
                "give it one, or load in append mode"
            )
        self._logger.info("purging database")
        await self._purger.purge(self._session)

    async def load(self, fixture: FixtureInterface) -> None:
        """Load ``fixture``, then flush what it added."""
        cls = type(fixture)
        name = f"{cls.__module__}.{cls.__qualname__}"
        if isinstance(fixture, OrderedFixtureInterface):
            self._logger.info(
                "loading [{order}] {fixture}", {"fixture": name, "order": fixture.get_order()}
            )
        else:
            self._logger.info("loading {fixture}", {"fixture": name})
        if isinstance(fixture, SharedFixtureInterface):
            fixture.set_reference_repository(self._references)
        await fixture.load(self._session)
        await self._session.flush()

    @abstractmethod
    async def execute(self, fixtures: Iterable[FixtureInterface], *, append: bool = False) -> None:
        """Empty the database unless ``append``, then load ``fixtures`` in the order given."""
