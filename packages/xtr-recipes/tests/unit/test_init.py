from __future__ import annotations

import xtr_recipes

_EXPECTED = {
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
}


def test_it_exports_its_public_api() -> None:
    assert set(xtr_recipes.__all__) == _EXPECTED


def test_every_exported_name_is_reachable() -> None:
    for name in xtr_recipes.__all__:
        assert hasattr(xtr_recipes, name)


def test_its_version_is_a_string() -> None:
    assert isinstance(xtr_recipes.__version__, str)
