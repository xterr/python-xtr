"""A SQLite database of the test's own, with the run table created."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from xtr_ai_orm_run_control import run_table

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from pathlib import Path


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


async def open_database(path: Path) -> AsyncEngine:
    """Open the SQLite file at ``path``, creating the run table on first use."""
    engine = create_async_engine(f"sqlite+aiosqlite:///{path}")
    metadata = MetaData()
    _ = run_table(metadata)
    async with engine.begin() as connection:
        await connection.run_sync(metadata.create_all)
    return engine


@pytest.fixture
async def engine(tmp_path: Path) -> AsyncIterator[AsyncEngine]:
    engine = await open_database(tmp_path / "ai.sqlite")
    try:
        yield engine
    finally:
        await engine.dispose()
