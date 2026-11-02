"""Building connections on a test's engine."""

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_orm_messenger.transport import Connection, OrmOptions

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
    from xtr_clock import ClockInterface


def engine_factory(engine: AsyncEngine) -> Callable[[], Awaitable[AsyncEngine]]:
    """Return what hands ``engine`` back, the shape a connection reaches its engine through."""

    async def provide() -> AsyncEngine:
        return engine

    return provide


def connection_on(
    engine: AsyncEngine,
    clock: ClockInterface,
    options: OrmOptions | None = None,
    session_factory: Callable[[], Awaitable[AsyncSession]] | None = None,
) -> Connection:
    """Return a connection on ``engine``, reading time from ``clock``."""
    return Connection(
        engine_factory(engine),
        options if options is not None else OrmOptions(),
        session_factory=session_factory,
        clock=clock,
    )
