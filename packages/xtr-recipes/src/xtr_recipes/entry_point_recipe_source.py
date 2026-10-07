"""The default recipe source: the installed distributions' entry points."""

from __future__ import annotations

import importlib.util
from importlib.metadata import entry_points
from pathlib import Path
from typing import TYPE_CHECKING, Final, final

from .exception import InvalidManifestError
from .normalise import normalise
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
# The one subtree a recipe's templates live in. Everything else in the package
# — its ``__init__.py``, bytecode written beside it, a stray editor file — is
# neither a template nor part of what the recipe applies, so it is read by
# nothing and left out of the hash: hashing it would move a hash between
# installs and churn the lock on nothing.
_FILES = "files"


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
            name = normalise(distribution.name)
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
    """Read a recipe package's manifest and the templates under ``files/``.

    Args:
        root: The recipe package, as a traversable tree.

    Returns:
        The manifest bytes and every file under ``files/``, keyed by its path
        under ``root`` (``files/...``). Nothing else in the package is read.
    """
    manifest = (root / _MANIFEST).read_bytes()
    files = root / _FILES
    templates = _read_templates(files, f"{_FILES}/") if files.is_dir() else {}
    return RecipeContent(manifest=manifest, templates=templates)


def _read_templates(node: Traversable, prefix: str) -> dict[str, bytes]:
    """Return every file under ``node``, keyed by its path with ``prefix``."""
    templates: dict[str, bytes] = {}
    for child in node.iterdir():
        path = f"{prefix}{child.name}"
        if child.is_dir():
            templates.update(_read_templates(child, f"{path}/"))
        else:
            templates[path] = child.read_bytes()
    return templates
