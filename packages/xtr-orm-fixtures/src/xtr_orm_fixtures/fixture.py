"""The base most fixtures derive from: one that shares objects with the rest of the run."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, override

from .exception import InvalidArgumentError
from .shared_fixture_interface import SharedFixtureInterface

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from .reference_repository import ReferenceRepository

__all__ = ["Fixture"]


class Fixture(SharedFixtureInterface, ABC):
    """A fixture handed the run's references, read and written through itself.

    Derive from it and write :meth:`load`; add
    :class:`~xtr_orm_fixtures.DependentFixtureInterface`,
    :class:`~xtr_orm_fixtures.OrderedFixtureInterface` or
    :class:`~xtr_orm_fixtures.FixtureGroupInterface` methods to place it in the
    run. It takes no constructor arguments of its own: a subclass's
    constructor is free for the services it needs.
    """

    _reference_repository: ReferenceRepository | None = None

    @abstractmethod
    @override
    async def load(self, session: AsyncSession) -> None:
        """Add this fixture's data to ``session``."""

    @override
    def set_reference_repository(self, repository: ReferenceRepository) -> None:
        """Keep ``repository``: the references of the run about to load this fixture."""
        self._reference_repository = repository

    def add_reference(self, name: str, obj: object) -> None:
        """Store ``obj`` under ``name``, which must not be taken for its class yet.

        Raises:
            ReferenceExistsError: If ``name`` is taken for ``obj``'s class.
            InvalidArgumentError: If no run has handed this fixture its references.
        """
        self._repository().add_reference(name, obj)

    def set_reference(self, name: str, obj: object) -> None:
        """Store ``obj`` under ``name``, replacing what was stored there for its class.

        Raises:
            InvalidArgumentError: If no run has handed this fixture its references.
        """
        self._repository().set_reference(name, obj)

    def get_reference[T](self, name: str, cls: type[T]) -> T:
        """Return the ``cls`` object stored under ``name``.

        Raises:
            ReferenceNotFoundError: If nothing is stored under ``name`` for ``cls``.
            InvalidArgumentError: If no run has handed this fixture its references.
        """
        return self._repository().get_reference(name, cls)

    def has_reference(self, name: str, cls: type) -> bool:
        """Whether an object is stored under ``name`` for ``cls``.

        Raises:
            InvalidArgumentError: If no run has handed this fixture its references.
        """
        return self._repository().has_reference(name, cls)

    def _repository(self) -> ReferenceRepository:
        repository = self._reference_repository
        if repository is None:
            raise InvalidArgumentError(
                f"{type(self).__qualname__} has no references yet: only a run hands a fixture "
                "the references it shares, just before it loads"
            )
        return repository
