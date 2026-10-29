"""Putting a test's directory first on the import path, for that test only."""

from __future__ import annotations

import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

__all__ = ["prepend_import_path"]


def prepend_import_path(monkeypatch: pytest.MonkeyPatch, directory: Path) -> None:
    """Import from ``directory`` first until the test ends."""
    monkeypatch.setattr(sys, "path", [str(directory), *sys.path])
    importlib.invalidate_caches()
