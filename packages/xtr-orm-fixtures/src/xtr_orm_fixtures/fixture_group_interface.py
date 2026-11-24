"""A fixture belonging to named groups, so a run can load only some."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from .fixture_interface import FixtureInterface

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["FixtureGroupInterface"]


@runtime_checkable
class FixtureGroupInterface(FixtureInterface, Protocol):
    """A fixture in the groups it names, besides the one named after its class.

    Asked of the class, so the groups are known before any fixture is built.
    """

    @classmethod
    def get_groups(cls) -> Sequence[str]:
        """Return the names of the groups this fixture belongs to."""
        ...
