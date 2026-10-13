"""Shared test fixtures."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.support.fake_backend import FakeBackends

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def backends() -> AsyncIterator[FakeBackends]:
    made = FakeBackends()
    yield made
    await made.close()
