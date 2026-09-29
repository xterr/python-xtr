"""Shared test fixtures. No test reaches a network: every backend runs locally."""

from __future__ import annotations

import pytest

pytest_plugins = ("tests.support.moto_server",)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
