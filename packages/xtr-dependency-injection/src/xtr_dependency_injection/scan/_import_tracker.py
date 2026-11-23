"""Recording which module reaches which, while a module is inspected — and tidying around each.

The tracker records, for every module whose body runs meanwhile, every
module it reached — which tells whether a set-aside module reaches the
package of a bundle that is not active, as one built on that bundle does,
and whether a module loaded meanwhile reached what the inspection served:

- through an ``import`` statement — ``builtins.__import__``, which every one
  calls;
- through ``importlib.import_module`` — the import system's ``_gcd_import``,
  which it looks up on every call, so a reference to it taken long before is
  seen too;
- by asking whether one exists, through ``importlib.util.find_spec``.

Each import is credited to the module whose body is running — not to the
module defining the function that imports, which may have been loaded long
before. Around each import call, it runs the callbacks it was given: the
inspection takes what it served for the statement before back out of
``sys.modules`` before one, so no import finds it there, and puts it back on
its packages after one, for the inspected body to reach by a dotted name.

It records, and calls back, only on the thread that opened it: an import
another thread makes meanwhile is passed on untouched.

Each is replaced while the tracker is open, passing every call on unchanged,
and put back when it closes — only if it is still the tracker's: a hook
installed over it meanwhile is left in place, and the tracker's own then
passes calls through without recording.

Private to the scan.
"""

from __future__ import annotations

import builtins
import importlib
import importlib.util
import sys
import threading
from typing import TYPE_CHECKING, Protocol, Self, final

from ._frames import running_module

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence
    from importlib.machinery import ModuleSpec
    from types import ModuleType, TracebackType

__all__ = ["ImportTracker"]


class _Import(Protocol):
    """What ``builtins.__import__`` is: the function every ``import`` statement calls."""

    def __call__(
        self,
        name: str,
        globals: Mapping[str, object] | None = None,  # noqa: A002 — the signature of builtins.__import__
        locals: Mapping[str, object] | None = None,  # noqa: A002 — the signature of builtins.__import__
        fromlist: Sequence[str] | None = (),
        level: int = 0,
    ) -> ModuleType: ...


@final
class ImportTracker:
    """Records what each module reached between opening and closing it.

    Attributes:
        imports: Each module whose body ran, mapped to the absolute names of
            the modules it imported or asked about.
    """

    __slots__ = (
        "_after",
        "_before",
        "_import_by_name",
        "_lookup",
        "_open",
        "_original",
        "_thread",
        "imports",
    )

    def __init__(
        self,
        before: Callable[[], None] | None = None,
        after: Callable[[], None] | None = None,
    ) -> None:
        """Record nothing until opened; call ``before`` and ``after`` around each import call."""
        self.imports: dict[str, set[str]] = {}
        self._before = before
        self._after = after
        self._original: _Import = builtins.__import__
        self._import_by_name: Callable[..., ModuleType] = _bootstrap().__dict__["_gcd_import"]
        self._lookup: Callable[..., ModuleSpec | None] = importlib.util.find_spec
        self._open = False
        self._thread = threading.get_ident()

    def __enter__(self) -> Self:
        """Start recording, on this thread; the tracker may be opened again once closed.

        A hook of this tracker's own still in place — left there by a tracker
        opened over it and closed after it — is not taken for the original.
        """
        bootstrap = _bootstrap().__dict__
        if builtins.__dict__["__import__"] != self._import:
            self._original = builtins.__import__
        if bootstrap["_gcd_import"] != self._tracked_import_by_name:
            self._import_by_name = bootstrap["_gcd_import"]
        if importlib.util.__dict__["find_spec"] != self._tracked_lookup:
            self._lookup = importlib.util.find_spec
        self._thread = threading.get_ident()
        self._open = True
        builtins.__dict__["__import__"] = self._import
        bootstrap["_gcd_import"] = self._tracked_import_by_name
        importlib.util.__dict__["find_spec"] = self._tracked_lookup
        return self

    def __exit__(
        self,
        kind: type[BaseException] | None,
        error: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Stop recording, and put back each function that is still the tracker's.

        The callbacks are let go: a module that kept a reference to one of the
        tracker's functions keeps nothing of the inspection through it.
        """
        del kind, error, traceback
        self._open = False
        self._before = None
        self._after = None
        _put_back(builtins.__dict__, "__import__", self._import, self._original)
        _put_back(
            _bootstrap().__dict__,
            "_gcd_import",
            self._tracked_import_by_name,
            self._import_by_name,
        )
        _put_back(importlib.util.__dict__, "find_spec", self._tracked_lookup, self._lookup)

    def _import(
        self,
        name: str,
        globals: Mapping[str, object] | None = None,  # noqa: A002 — the signature of builtins.__import__
        locals: Mapping[str, object] | None = None,  # noqa: A002 — the signature of builtins.__import__
        fromlist: Sequence[str] | None = (),
        level: int = 0,
    ) -> ModuleType:
        tracking = self._starting()
        imported = self._original(name, globals, locals, fromlist, level)
        if tracking:
            importer = running_module()
            if importer is None and globals is not None:
                found = globals.get("__name__")
                importer = found if isinstance(found, str) else None
            if importer is not None:
                self._record(importer, name, imported, fromlist)
            self._ended()
        return imported

    def _tracked_import_by_name(
        self, name: str, package: str | None = None, level: int = 0
    ) -> ModuleType:
        tracking = self._starting()
        imported = self._import_by_name(name, package, level)
        if tracking:
            importer = running_module()
            if importer is not None:
                self.imports.setdefault(importer, set()).add(imported.__name__)
            self._ended()
        return imported

    def _tracked_lookup(self, name: str, package: str | None = None) -> ModuleSpec | None:
        tracking = self._starting()
        importer = running_module() if tracking else None
        if importer is not None:
            absolute = importlib.util.resolve_name(name, package) if name.startswith(".") else name
            self.imports.setdefault(importer, set()).add(absolute)
        found = self._lookup(name, package)
        if tracking:
            self._ended()
        return found

    def _starting(self) -> bool:
        """Call back before an import call of the tracking thread; return whether to record it."""
        tracking = self._open and threading.get_ident() == self._thread
        if tracking and self._before is not None:
            self._before()
        return tracking

    def _ended(self) -> None:
        """Call back after an import call of the tracking thread that succeeded."""
        if self._open and self._after is not None:
            self._after()

    def _record(
        self, importer: str, name: str, imported: ModuleType, fromlist: Sequence[str] | None
    ) -> None:
        """Record what ``importer`` reached: the module named, and each name it took from it.

        A ``from`` import — every relative import is one — is handed back the
        module it names, so that module's own name is the absolute one; any
        other import names its module absolutely already. Each name taken is
        recorded under it, a submodule or not: one taken from a package's
        attribute never shows in ``sys.modules`` as imported.
        """
        target = getattr(imported, "__name__", None) if fromlist else name
        if not isinstance(target, str):
            return
        reached = self.imports.setdefault(importer, set())
        reached.add(target)
        reached.update(f"{target}.{item}" for item in fromlist or () if item != "*")


def _bootstrap() -> ModuleType:
    """Return the import system's own module, whose ``_gcd_import`` loads a module by name."""
    return sys.modules["importlib._bootstrap"]


def _put_back(namespace: dict[str, object], name: str, ours: object, original: object) -> None:
    """Put ``original`` back as ``namespace[name]``, unless a hook replaced ``ours`` meanwhile.

    Set through the namespace: a type checker takes each of these for the one
    function it is declared as, so no other may be assigned to the attribute.
    """
    if namespace.get(name) == ours:
        namespace[name] = original
