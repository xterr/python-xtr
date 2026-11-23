"""Refusing to load a set-aside module, for the length of one inspecting scan.

A module set aside is not loaded: importing it fails, as it would at runtime.
While the scan goes on, its file is still there to be found, and finding it
would run it again — truthfully, so failing again, or worse, half-way. One
:class:`RefusalFinder`, first of all finders, keeps that from happening: a
name that is, or lies under, a set-aside module is refused with
:class:`SetAsideRefused`, which any ``except ImportError`` catches.

It serves nothing. Asked only whether such a module exists
(``importlib.util.find_spec``), it answers as the other finders do, with the
record they found — whose loader refuses to load it.

Private to the scan.
"""

from __future__ import annotations

import importlib.abc
import sys
import threading
from typing import TYPE_CHECKING, final, override

if TYPE_CHECKING:
    from collections.abc import Collection, Sequence
    from importlib.machinery import ModuleSpec
    from types import ModuleType

__all__ = ["RefusalFinder", "SetAsideRefused", "holder_of"]


@final
class SetAsideRefused(ModuleNotFoundError):  # noqa: N818 — named for what the scan did, as its report is
    """Raised by an import of a set-aside module, or of one lying under a set-aside package.

    It names no module, as the error of a module that needs a missing package
    does not name that module: ``from package import module`` takes an error
    naming the module itself for "no such module", and goes on.

    Attributes:
        module: The module refused.
        through: The set-aside module the name is, or lies under.
    """

    def __init__(self, module: str, through: str) -> None:
        """Refuse ``module``, set aside as, or under, ``through``."""
        super().__init__(f"{module!r} is set aside: a package it needs is not installed")
        self.module = module
        self.through = through


def holder_of(module: str, packages: Collection[str]) -> str | None:
    """Return the one of ``packages`` that ``module`` is, or lies in; ``None`` if none."""
    return next(
        (package for package in packages if module == package or module.startswith(f"{package}.")),
        None,
    )


@final
class _RefusingLoader(importlib.abc.Loader):
    """Loads nothing: the module it was found for is set aside."""

    def __init__(self, through: str) -> None:
        self._through = through

    @override
    def create_module(self, spec: ModuleSpec) -> ModuleType | None:
        # Raised before the import system puts anything in sys.modules.
        raise SetAsideRefused(spec.name, self._through)

    @override
    def exec_module(self, module: ModuleType) -> None:
        raise SetAsideRefused(module.__name__, self._through)


@final
class RefusalFinder(importlib.abc.MetaPathFinder):
    """Refuses every set-aside module, on the thread that created it.

    Placed first on ``sys.meta_path`` for the scan's length. It reads the
    names set aside from the collection it was given, as that grows.
    """

    def __init__(self, set_aside: Collection[str]) -> None:
        """Refuse each name of ``set_aside``, and every name under one."""
        self._set_aside = set_aside
        self._thread = threading.get_ident()

    @override
    def find_spec(
        self,
        fullname: str,
        path: Sequence[str] | None,
        target: ModuleType | None = None,
    ) -> ModuleSpec | None:
        """Answer for a set-aside name with a record refusing to load; else ``None``."""
        if threading.get_ident() != self._thread:
            return None
        through = holder_of(fullname, self._set_aside)
        if through is None:
            return None
        for finder in sys.meta_path:
            if finder is self:
                continue
            found = finder.find_spec(fullname, path, target)
            if found is not None:
                # A record made for this call: its loader is replaced, nothing else of it.
                found.loader = _RefusingLoader(through)
                return found
        return None

    def install(self) -> None:
        """Go first of all finders."""
        sys.meta_path.insert(0, self)

    def remove(self) -> None:
        """Leave ``sys.meta_path``, if still there."""
        if self in sys.meta_path:
            sys.meta_path.remove(self)
