"""Shared test fixtures. Every database is a SQLite file under the test's own directory."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from pathlib import Path


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def database_url(tmp_path: Path) -> str:
    return f"sqlite+aiosqlite:///{tmp_path / 'app.sqlite'}"


@pytest.fixture
async def engine(database_url: str) -> AsyncIterator[AsyncEngine]:
    # The driver's own transaction handling, so a rolled-back run leaves nothing behind.
    built = create_async_engine(database_url, connect_args={"autocommit": False})
    yield built
    await built.dispose()
