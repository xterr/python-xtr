"""A package's *Use in an application* steps, applied to a project by a command.

Every package that ships a bundle also ships a recipe beside it — the bundle to
list, the configuration file to write, the environment variables to set and the
ignore lines to add. A recipe is declarative, so the same description that
configures an application also says, read backwards, how to unconfigure it.

The command ``xtr-recipes recipes:sync`` reads the recipes of the application's
direct dependencies, diffs them against a committed lock file, and applies the
difference: nothing cares how a package arrived, and running it twice changes
nothing the second time.

This module exposes the pieces that read a project, parse a recipe, read or
write the lock, and compute the plan that applies the difference. The commands
that drive them live in :mod:`xtr_recipes.command`, behind the ``xtr-recipes``
console script.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from .bundle_entry import BundleEntry
from .bundle_planner import BundlePlanner
from .bundle_requirements import BundleRequirements
from .bundles_file import BundlesFile
from .entry_point_recipe_source import RECIPES_ENTRY_POINT_GROUP, EntryPointRecipeSource
from .exception import (
    BundlesNotEditableError,
    InvalidManifestError,
    MarkedBlockError,
    ProjectNotFoundError,
    RecipeNotInstalledError,
    RecipesError,
    UnreadableFileError,
    UnsafePathError,
)
from .marked_block_editor import MarkedBlockEditor
from .notes_config import NotesConfig
from .operation import OperationInterface, Plan
from .planned_recipe import PlannedRecipe
from .project import Project
from .recipe_config import RecipeConfig
from .recipe_content import RecipeContent
from .recipe_loader import Recipe, RecipeLoader
from .recipe_lock import BundleState, LockedFile, LockEntry, RecipeLock
from .recipe_planner import RecipePlanner
from .recipe_source_interface import RecipeSourceInterface
from .recipe_survey import RecipeSurvey
from .sync_draft import SyncDraft
from .sync_options import SyncOptions
from .sync_selection import SyncSelection
from .synchronizer import Synchronizer

try:
    __version__ = version("xtr-recipes")
except PackageNotFoundError:  # pragma: no cover
    # Running from a source tree with no installed metadata to read. Having no
    # version is better than refusing to import.
    __version__ = "0+unknown"

__all__ = [
    "RECIPES_ENTRY_POINT_GROUP",
    "BundleEntry",
    "BundlePlanner",
    "BundleRequirements",
    "BundleState",
    "BundlesFile",
    "BundlesNotEditableError",
    "EntryPointRecipeSource",
    "InvalidManifestError",
    "LockEntry",
    "LockedFile",
    "MarkedBlockEditor",
    "MarkedBlockError",
    "NotesConfig",
    "OperationInterface",
    "Plan",
    "PlannedRecipe",
    "Project",
    "ProjectNotFoundError",
    "Recipe",
    "RecipeConfig",
    "RecipeContent",
    "RecipeLoader",
    "RecipeLock",
    "RecipeNotInstalledError",
    "RecipePlanner",
    "RecipeSourceInterface",
    "RecipeSurvey",
    "RecipesError",
    "SyncDraft",
    "SyncOptions",
    "SyncSelection",
    "Synchronizer",
    "UnreadableFileError",
    "UnsafePathError",
    "__version__",
]
