"""A fixture placed in the run by a number."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .fixture_interface import FixtureInterface

__all__ = ["OrderedFixtureInterface"]


@runtime_checkable
class OrderedFixtureInterface(FixtureInterface, Protocol):
    """A fixture loaded in the order of its number, lowest first.

    Numbered fixtures load before the others. A fixture is ordered by a number
    or by its dependencies, never by both.
    """

    def get_order(self) -> int:
        """Return this fixture's place in the run: lower loads sooner."""
        ...
