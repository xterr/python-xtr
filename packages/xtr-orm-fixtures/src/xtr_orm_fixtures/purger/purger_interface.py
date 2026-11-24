"""What empties a database before fixtures load."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

__all__ = ["PurgerInterface"]


@runtime_checkable
class PurgerInterface(Protocol):
    """Empties the tables fixtures load into, on the session of the run."""

    async def purge(self, session: AsyncSession) -> None:
        """Empty the tables through ``session``, without committing.

        The run that called it commits or rolls back, so an emptying that
        fails half-way, or fixtures that fail after it, leave the database as
        it was wherever the database can take the statements back.
        """
        ...
