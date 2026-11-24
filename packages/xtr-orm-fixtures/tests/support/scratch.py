"""Throwaway modules on ``sys.path`` for one test, and a package taken off it.

An application whose modules import a library a test may leave out is written
by the test, not kept under ``tests/``: what is installed differs from one test
to the next, and nothing written stays loaded once the test ends.
"""

from __future__ import annotations

import importlib
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

    import pytest

__all__ = ["ScratchSite", "hide_package"]


@dataclass(frozen=True, slots=True)
class ScratchSite:
    """A directory whose modules a test writes, importable while it is on ``sys.path``."""

    root: Path

    def write(self, modules: Mapping[str, str]) -> None:
        """Write each module, by dotted name (``.__init__`` for a package's own), with source."""
        for module, source in modules.items():
            *packages, leaf = module.split(".")
            directory = self.root
            for package in packages:
                directory /= package
                directory.mkdir(parents=True, exist_ok=True)
                init = directory / "__init__.py"
                if not init.exists():
                    _ = init.write_text("")
            _ = (directory / f"{leaf}.py").write_text(source)
        importlib.invalidate_caches()

    def install(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Put the directory on ``sys.path`` until the test ends."""
        self.root.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(sys, "path", [str(self.root), *sys.path])
        importlib.invalidate_caches()

    def unload(self) -> None:
        """Take every module loaded from the directory out of ``sys.modules``."""
        for name, module in list(sys.modules.items()):
            origin = getattr(module, "__file__", None)
            if isinstance(origin, str) and origin.startswith(str(self.root)):
                del sys.modules[name]
        importlib.invalidate_caches()


def hide_package(monkeypatch: pytest.MonkeyPatch, package: str) -> None:
    """Make ``package`` look not installed until the test ends.

    Its directory leaves ``sys.path`` and its modules leave ``sys.modules``:
    importing it fails, and ``importlib.util.find_spec`` finds nothing, as on
    an installation without it. Both come back when the test ends.
    """
    module = importlib.import_module(package)
    location = Path(str(module.__file__)).resolve().parents[1]
    kept = [entry for entry in sys.path if Path(entry or ".").resolve() != location]
    monkeypatch.setattr(sys, "path", kept)
    for name in [name for name in sys.modules if name.partition(".")[0] == package]:
        monkeypatch.delitem(sys.modules, name)
    importlib.invalidate_caches()
