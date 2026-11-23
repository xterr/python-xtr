"""Who imports: what an import hook asks, since it is not told.

Two questions, both answered from the call stack:

- :func:`running_module` — whose module body is running: the innermost
  module body on the stack belongs to the module whose import is under way,
  and every frame nearer is the import system's, a hook's, or a function that
  module called;
- :func:`importing_module` — whose code made the import: the nearest frame
  that is neither the import system's nor one of the scan's own hooks.

Private to the package.
"""

from __future__ import annotations

import inspect
from typing import Final

__all__ = ["importing_module", "running_module"]

_HOOK_MODULES: Final = frozenset(
    {
        "importlib",
        "importlib.util",
        "importlib._bootstrap",
        "importlib._bootstrap_external",
        "xtr_dependency_injection.scan._frames",
        "xtr_dependency_injection.scan._import_tracker",
        "xtr_dependency_injection.scan._stand_ins",
    }
)
"""The modules an import passes through on its way to a finder: never the importer."""


def running_module() -> str | None:
    """Return the name of the module whose body is running, or ``None`` outside one."""
    frame = inspect.currentframe()
    while frame is not None and frame.f_code.co_name != "<module>":
        frame = frame.f_back
    if frame is None:
        return None
    name = frame.f_globals.get("__name__")
    return name if isinstance(name, str) else None


def importing_module() -> str | None:
    """Return the name of the module whose code made the import under way, or ``None``.

    ``None`` too for code run with globals naming no module — ``exec`` of a
    string with a bare namespace.
    """
    frame = inspect.currentframe()
    while frame is not None:
        name = frame.f_globals.get("__name__")
        frozen = frame.f_code.co_filename.startswith("<frozen importlib")
        if not frozen and name not in _HOOK_MODULES:
            return name if isinstance(name, str) else None
        frame = frame.f_back
    return None
