"""Shared test fixtures."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from tests.support.import_path import prepend_import_path

if TYPE_CHECKING:
    from collections.abc import Iterator

FIXTURES = Path(__file__).parent / "fixtures"
"""Where the templates the tests render live."""


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def importable() -> Iterator[None]:
    """Forget, after the test, every module a test project put in ``sys.modules``.

    Looking a dotted package up imports its parents, which would otherwise
    stay cached at the first test's temporary directory.
    """
    before = set(sys.modules)
    yield
    for name in set(sys.modules) - before:
        del sys.modules[name]
    importlib.invalidate_caches()


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, importable: None) -> Path:
    """An application laid out with its package under ``src/``: ``src/app/``, importable."""
    del importable
    _ = (tmp_path / "pyproject.toml").write_text('[project]\nname = "app"\n', encoding="utf-8")
    package = tmp_path / "src" / "app"
    package.mkdir(parents=True)
    _ = (package / "__init__.py").write_text('"""The app."""\n', encoding="utf-8")
    prepend_import_path(monkeypatch, tmp_path / "src")
    return tmp_path
