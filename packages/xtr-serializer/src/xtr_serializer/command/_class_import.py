"""Finding the class a command line names, by its module and its name."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from types import ModuleType

__all__ = ["import_class"]

_MISSING: Final = object()


def import_class(path: str) -> type | str:
    """Import the class ``path`` names, or say why it cannot be.

    ``path`` is ``module:Class`` — the class's name may hold dots, for a class inside another —
    or ``module.Class``, in which the module is the longest leading part that is one. A module
    that cannot be found is told from one that fails as it is imported, which says why.
    """
    module_name, colon, attribute = path.partition(":")
    parts = path.split(".")
    if colon:
        splits = [(module_name, attribute)]
        parts = [*module_name.split("."), *attribute.split(".")]
    else:
        splits = [
            (".".join(parts[:end]), ".".join(parts[end:])) for end in range(len(parts) - 1, 0, -1)
        ]
    if not splits or not all(parts):
        return f"{path!r} names no class: write it module:Class, or module.Class"
    for candidate, attribute_path in splits:
        module = _module(candidate)
        if isinstance(module, str):
            return module
        if module is not None:
            return _class_in(module, candidate, attribute_path, path)
    if colon:
        return f"no module {module_name!r} can be imported"
    return f"no module of {path!r} can be imported"


def _module(name: str) -> ModuleType | str | None:
    """Import the module ``name``: ``None`` when there is none, why when importing it fails."""
    try:
        return import_module(name)
    except ModuleNotFoundError as error:
        missing = error.name or ""
        if name == missing or name.startswith(missing + "."):
            return None
        return f"{name!r} cannot be imported: {error}"
    except ImportError as error:
        return f"{name!r} cannot be imported: {error}"


def _class_in(module: ModuleType, module_name: str, attribute: str, path: str) -> type | str:
    """Find the class ``attribute`` names in ``module``, or say why it is none."""
    found: object = module
    for name in attribute.split("."):
        found = getattr(found, name, _MISSING)
        if found is _MISSING:
            return f"{module_name!r} has no {attribute!r}"
    if not isinstance(found, type):
        return f"{path!r} is a {type(found).__name__}, not a class"
    return found
