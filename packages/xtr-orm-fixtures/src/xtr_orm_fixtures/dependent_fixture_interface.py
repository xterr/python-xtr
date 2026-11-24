"""A fixture loaded after the fixtures it names."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from .fixture_interface import FixtureInterface

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["DependentFixtureInterface"]


@runtime_checkable
class DependentFixtureInterface(FixtureInterface, Protocol):
    """A fixture needing others loaded first — those whose references it reads.

    A fixture is ordered by its dependencies or by a number, never by both.
    """

    def get_dependencies(self) -> Sequence[type[FixtureInterface]]:
        """Return the fixture classes to load before this one; never empty, never this one."""
        ...
