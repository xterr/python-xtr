"""Shared test fixtures."""

from __future__ import annotations

import pytest

from tests.support.bound_instants import record_bound_instants


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def bound_instants(monkeypatch: pytest.MonkeyPatch) -> list[object]:
    """Every instant a stored credential's column hands its driver, east of UTC."""
    return record_bound_instants(monkeypatch)
