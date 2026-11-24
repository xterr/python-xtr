"""Fixtures depend on one another in a circle, so none of them can be loaded first."""

from __future__ import annotations

from .orm_fixtures_error import OrmFixturesError

__all__ = ["CircularReferenceError"]


class CircularReferenceError(OrmFixturesError):
    """Fixtures depend on one another in a circle, so none of them can be loaded first.

    Attributes:
        fixtures: The fixtures in the circle, by name, in the order they depend
            on one another; the first is named again at the end.
    """

    fixtures: tuple[str, ...]

    def __init__(self, fixtures: tuple[str, ...]) -> None:
        """Record the fixtures in the circle."""
        self.fixtures = fixtures
        circle = " -> ".join(fixtures)
        super().__init__(f"The fixtures depend on one another in a circle: {circle}.")
