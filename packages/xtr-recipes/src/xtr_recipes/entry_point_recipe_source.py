"""The default recipe source: the installed distributions' entry points."""

from __future__ import annotations

import importlib.util
import re
from importlib.metadata import entry_points
from pathlib import Path
from typing import TYPE_CHECKING, Final, final

from .exception import InvalidManifestError
from .recipe_content import RecipeContent

if TYPE_CHECKING:
    from importlib.resources.abc import Traversable

__all__ = ["RECIPES_ENTRY_POINT_GROUP", "EntryPointRecipeSource", "read_recipe_content"]

RECIPES_ENTRY_POINT_GROUP: Final = "xtr_recipes"
"""The entry point group a distribution advertises its recipe package under.

A distribution ships ``<bundle name> = "xtr_<name>.recipe"`` here; the value is
a package path. It is located on disk, never imported: importing it would run
the package's own ``__init__``, and one package that fails to import must not
stop every other recipe from being read.
"""

_MANIFEST = "manifest.toml"
# Bytecode written beside an installed recipe carries the interpreter version
# and the source's timestamp: hashing it would move a hash between installs.
_BYTECODE = "__pycache__"
# PEP 503 normalisation: a run of dashes, underscores or dots is one separator.
_SEPARATORS = re.compile(r"[-_.]+")


@final
class EntryPointRecipeSource:
    """Reads each distribution's recipe from its ``xtr_recipes`` entry point."""

    def load(self) -> dict[str, RecipeContent]:
        """Return every advertised recipe, keyed by normalised distribution name."""
        result: dict[str, RecipeContent] = {}
        for entry in entry_points(group=RECIPES_ENTRY_POINT_GROUP):
            distribution = entry.dist
            if distribution is None:
                continue
            name = _normalise(distribution.name)
            result[name] = read_recipe_content(_locate(name, entry.module))
        return result


def _locate(distribution: str, module: str) -> Path:
    """Return the directory of the recipe package ``module`` names, importing nothing.

    Only the top-level package is looked up — locating a top-level package does
    not execute it — and the rest of the dotted path is followed on disk, which
    is how an installed wheel and an editable install both lay it out.
    """
    top, *rest = module.split(".")
    found = importlib.util.find_spec(top)
    locations = found.submodule_search_locations if found is not None else None
    if not locations:
        raise InvalidManifestError(distribution, module, "no such package is installed")
    return Path(next(iter(locations))).joinpath(*rest)


def read_recipe_content(root: Traversable) -> RecipeContent:
    """Read a recipe package's manifest and templates from its root.

    Args:
        root: The recipe package, as a traversable tree.

    Returns:
        The manifest bytes and every other file keyed by its path under
        ``root``.
    """
    manifest = (root / _MANIFEST).read_bytes()
    return RecipeContent(manifest=manifest, templates=_read_templates(root, ""))


def _read_templates(node: Traversable, prefix: str) -> dict[str, bytes]:
    """Return every file under ``node`` except the manifest and bytecode, by path."""
    templates: dict[str, bytes] = {}
    for child in node.iterdir():
        path = f"{prefix}{child.name}"
        if child.name == _BYTECODE:
            continue
        if child.is_dir():
            templates.update(_read_templates(child, f"{path}/"))
        elif child.name != _MANIFEST:
            templates[path] = child.read_bytes()
    return templates


def _normalise(name: str) -> str:
    """Return the PEP 503-normalised form of a distribution name."""
    return _SEPARATORS.sub("-", name).lower()
