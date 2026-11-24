"""A fixture sharing objects with the others of a run, by name."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from .fixture_interface import FixtureInterface

if TYPE_CHECKING:
    from .reference_repository import ReferenceRepository

__all__ = ["SharedFixtureInterface"]


@runtime_checkable
class SharedFixtureInterface(FixtureInterface, Protocol):
    """A fixture handed the run's references before it loads.

    One repository serves every fixture of a run, so an object one stores
    under a name is the one a later fixture reads under it.
    """

    def set_reference_repository(self, repository: ReferenceRepository) -> None:
        """Keep ``repository``: the references of the run about to load this fixture."""
        ...
