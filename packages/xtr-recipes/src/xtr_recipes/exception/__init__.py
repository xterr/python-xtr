"""Every error this library raises.

All of them derive from :class:`RecipesError`, so one ``except`` catches
anything applying a recipe can go wrong with, and a narrower one handles a
single cause. Each carries the data a caller needs as typed attributes rather
than forcing a message to be parsed.
"""

from __future__ import annotations

from .bundles_not_editable_error import BundlesNotEditableError
from .invalid_manifest_error import InvalidManifestError
from .marked_block_error import MarkedBlockError
from .project_not_found_error import ProjectNotFoundError
from .recipe_not_installed_error import RecipeNotInstalledError
from .recipes_error import RecipesError

__all__ = [
    "BundlesNotEditableError",
    "InvalidManifestError",
    "MarkedBlockError",
    "ProjectNotFoundError",
    "RecipeNotInstalledError",
    "RecipesError",
]
