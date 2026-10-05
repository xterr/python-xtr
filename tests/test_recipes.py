"""Every package that ships a bundle ships a recipe an application can apply.

A package advertises its bundle under the ``xtr_dependency_injection.bundles``
entry-point group; a recipe for it is advertised under ``xtr_recipes``, named
the same and pointing at the ``recipe`` subpackage beside the bundle. The checks
here read the source tree directly, so a recipe has to agree with the bundle it
accompanies before anything is installed: the entry points line up, the manifest
parses, every bundle it lists is one the package advertises, and every template
it writes is on disk.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import cast

import pytest
from xtr_recipes.recipe_config import RecipeConfig

_ROOT = Path(__file__).resolve().parents[1]
_BUNDLES_GROUP = "xtr_dependency_injection.bundles"
_RECIPES_GROUP = "xtr_recipes"


def _table(value: object) -> dict[str, object]:
    """Return ``value`` as a table of string keys, or an empty one."""
    if not isinstance(value, dict):
        return {}
    narrowed = cast("dict[object, object]", value)
    return {str(key): item for key, item in narrowed.items()}


def _pyproject(package_dir: Path) -> dict[str, object]:
    """Read one package's ``pyproject.toml`` into a table."""
    with (package_dir / "pyproject.toml").open("rb") as handle:
        return _table(tomllib.load(handle))


def _entry_points(data: dict[str, object], group: str) -> dict[str, str]:
    """Return the ``group`` entry points, each name mapped to its target."""
    groups = _table(_table(data.get("project")).get("entry-points"))
    return {name: str(target) for name, target in _table(groups.get(group)).items()}


def _recipe_dir(package_dir: Path, recipe_target: str) -> Path:
    """Return the recipe subpackage directory a ``xtr_recipes`` target names."""
    return package_dir.joinpath("src", *recipe_target.split("."))


def _manifest(recipe_dir: Path) -> RecipeConfig:
    """Parse the recipe's ``manifest.toml`` through the library's own parser."""
    with (recipe_dir / "manifest.toml").open("rb") as handle:
        return RecipeConfig.from_toml(recipe_dir.parents[1].name, _table(tomllib.load(handle)))


_PACKAGES = sorted(
    (
        path.parent
        for path in _ROOT.glob("packages/*/pyproject.toml")
        if _entry_points(_pyproject(path.parent), _BUNDLES_GROUP)
    ),
    key=lambda path: path.name,
)


def _id(package_dir: Path) -> str:
    return package_dir.name


def test_bundle_packages_are_found() -> None:
    assert _PACKAGES


@pytest.mark.parametrize("package_dir", _PACKAGES, ids=_id)
def test_recipe_entry_point_matches_the_bundle(package_dir: Path) -> None:
    data = _pyproject(package_dir)
    bundles = _entry_points(data, _BUNDLES_GROUP)
    recipes = _entry_points(data, _RECIPES_GROUP)

    assert recipes.keys() == bundles.keys()
    for name, target in bundles.items():
        root = target.split(".", 1)[0]
        assert recipes[name] == f"{root}.recipe"


@pytest.mark.parametrize("package_dir", _PACKAGES, ids=_id)
def test_manifest_parses_and_matches_the_bundle(package_dir: Path) -> None:
    data = _pyproject(package_dir)
    bundles = _entry_points(data, _BUNDLES_GROUP)
    recipes = _entry_points(data, _RECIPES_GROUP)

    for name, recipe_target in recipes.items():
        recipe_dir = _recipe_dir(package_dir, recipe_target)
        config = _manifest(recipe_dir)

        assert bundles[name] in config.bundles
        for template in config.files.values():
            assert (recipe_dir / template).is_file(), f"{package_dir.name}: {template}"


@pytest.mark.parametrize("package_dir", _PACKAGES, ids=_id)
def test_every_listed_bundle_is_advertised(package_dir: Path) -> None:
    data = _pyproject(package_dir)
    advertised = set(_entry_points(data, _BUNDLES_GROUP).values())

    for recipe_target in _entry_points(data, _RECIPES_GROUP).values():
        config = _manifest(_recipe_dir(package_dir, recipe_target))
        assert set(config.bundles) <= advertised
