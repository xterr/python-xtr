"""What every fixture is: something that loads data into a session."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

__all__ = ["FixtureInterface"]


@runtime_checkable
class FixtureInterface(Protocol):
    """Loads data into a session.

    The only thing a fixture must do. The run commits, or rolls back, once,
    after every fixture has loaded: a fixture adds and flushes, it does not
    commit.
    """

    async def load(self, session: AsyncSession) -> None:
        """Add this fixture's data to ``session``."""
        ...
