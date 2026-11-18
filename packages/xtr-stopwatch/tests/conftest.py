from __future__ import annotations

import pytest
from xtr_clock import MockClock


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def clock() -> MockClock:
    return MockClock("2026-01-01 00:00:00")
