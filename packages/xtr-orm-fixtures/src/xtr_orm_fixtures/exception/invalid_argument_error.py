"""A call was given something the library cannot work with."""

from __future__ import annotations

from .orm_fixtures_error import OrmFixturesError

__all__ = ["InvalidArgumentError"]


class InvalidArgumentError(OrmFixturesError, ValueError):
    """A call was given something the library cannot work with.

    Raised where the value is given — an unknown purger, a fixture asked for a
    reference before a run gave it one — rather than later, when the database
    is reached.

    Also a :class:`ValueError`, so code that already guards its input with
    ``except ValueError`` keeps working without learning a new exception.

    Attributes:
        reason: What is wrong with the value.
    """

    reason: str

    def __init__(self, reason: str) -> None:
        """Record what is wrong with the value."""
        self.reason = reason
        super().__init__(reason)
