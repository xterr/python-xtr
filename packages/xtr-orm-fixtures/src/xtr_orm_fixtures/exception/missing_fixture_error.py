"""A fixture depends on one that was never added to the loader."""

from __future__ import annotations

from .orm_fixtures_error import OrmFixturesError

__all__ = ["MissingFixtureError"]


class MissingFixtureError(OrmFixturesError, LookupError):
    """A fixture depends on one that was never added to the loader.

    Also a :class:`LookupError`, as a missing key in any other mapping is.

    Attributes:
        fixture: The fixture depended on, by name.
        required_by: The fixture depending on it, by name.
    """

    fixture: str
    required_by: str

    def __init__(self, fixture: str, required_by: str) -> None:
        """Record the fixture missing and the one depending on it."""
        self.fixture = fixture
        self.required_by = required_by
        super().__init__(
            f'The fixture "{required_by}" depends on "{fixture}", which was not added; '
            "add it, or remove the dependency."
        )
