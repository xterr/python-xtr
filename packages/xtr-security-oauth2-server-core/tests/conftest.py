"""Shared test fixtures."""

from __future__ import annotations

import pytest

__all__ = ["anyio_backend"]


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
