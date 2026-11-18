"""Shared test fixtures."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(autouse=True)
def folder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Where the fixture application keeps its profiles: a folder of the test's own."""
    monkeypatch.setenv("PROFILER_TEST_FOLDER", str(tmp_path))
    return tmp_path
