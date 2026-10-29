"""Shared test fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
"""Where the templates the tests render live."""


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """An application laid out with its package under ``src/``: ``src/app/``."""
    _ = (tmp_path / "pyproject.toml").write_text('[project]\nname = "app"\n', encoding="utf-8")
    package = tmp_path / "src" / "app"
    package.mkdir(parents=True)
    _ = (package / "__init__.py").write_text('"""The app."""\n', encoding="utf-8")
    return tmp_path
