"""How many rows a statement changed, as the driver reported it."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from sqlalchemy import Column, MetaData, String, Table, delete, update
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from xtr_security_oauth2_server.manager.orm._changed_rows import changed_rows

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator
    from pathlib import Path

pytestmark = pytest.mark.anyio

_TABLE = Table(
    "rows",
    MetaData(),
    Column("identifier", String(8), primary_key=True),
    Column("flagged", String(8), nullable=True),
)


async def _three(tmp_path: Path) -> AsyncGenerator[AsyncSession, None]:
    """Yield a session over a table holding three rows, two of them flagged."""
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'rows.sqlite'}")
    try:
        async with engine.begin() as connection:
            await connection.run_sync(_TABLE.metadata.create_all)
        async with AsyncSession(engine) as session:
            for identifier, flagged in (("one", "yes"), ("two", "yes"), ("three", None)):
                _ = await session.execute(
                    _TABLE.insert().values(identifier=identifier, flagged=flagged),
                )
            await session.commit()
            yield session
    finally:
        await engine.dispose()


async def test_it_reports_the_rows_an_update_changed(tmp_path: Path) -> None:
    async for session in _three(tmp_path):
        changed = await session.execute(
            update(_TABLE).where(_TABLE.c["flagged"] == "yes").values(flagged="no"),
        )

        assert changed_rows(changed) == 2


async def test_it_reports_nothing_when_a_statement_matched_nothing(tmp_path: Path) -> None:
    async for session in _three(tmp_path):
        changed = await session.execute(
            update(_TABLE).where(_TABLE.c["identifier"] == "four").values(flagged="no"),
        )

        assert changed_rows(changed) == 0


async def test_it_reports_the_rows_a_delete_removed(tmp_path: Path) -> None:
    async for session in _three(tmp_path):
        removed = await session.execute(delete(_TABLE).where(_TABLE.c["flagged"].is_(None)))

        assert changed_rows(removed) == 1
