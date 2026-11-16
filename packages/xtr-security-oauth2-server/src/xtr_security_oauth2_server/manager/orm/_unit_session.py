"""The session of a unit of work of the server's own, opened for one read or write."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from xtr_dependency_injection import ScopeFactoryInterface

__all__ = ["unit_session"]


@asynccontextmanager
async def unit_session(
    scope_factory: ScopeFactoryInterface, connection: str
) -> AsyncGenerator[AsyncSession]:
    """Open a unit of work of its own, and yield its session on ``connection``.

    Never the unit of the request being served: committing what the server
    stores there would commit whatever the application has pending, and a
    rollback of the request would take back a credential already handed out.
    The unit is a full one — its session is built as the application
    configured it, the unit participants are told of it, and it is closed
    when the block ends — so a write commits before the block ends.
    """
    async with scope_factory.unit_of_work(join=False) as unit:
        yield await unit.get(AsyncSession, connection)
