"""Every package that ships a bundle ships a recipe an application can apply.

A package ships a bundle when a module under its ``src`` declares one; that is what is
searched for here, rather than the entry points, so a bundle nobody advertised is found
too. Such a package advertises its bundle under the ``xtr_dependency_injection.bundles``
entry-point group and a recipe for it under ``xtr_recipes``, named the same and pointing at
the ``recipe`` subpackage beside the bundle. The checks read the source tree directly, so a
recipe has to agree with the bundle it accompanies before anything is installed: the entry
points line up, the manifest parses, every bundle it lists is one the package advertises,
every template it writes is on disk, and what it writes into an application is what the
README's *Use in an application* section promises.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path
from typing import cast

import pytest
from xtr_recipes.exception import InvalidManifestError
from xtr_recipes.recipe_config import RecipeConfig

_ROOT = Path(__file__).resolve().parents[1]
_BUNDLES_GROUP = "xtr_dependency_injection.bundles"
_RECIPES_GROUP = "xtr_recipes"
# AGENTS.md exempts the kernel's own bundle from both groups: it is the container the entry
# points are read by, so announcing it to debug:bundles as a discoverable peer would be
# redundant, and there is nothing for a recipe to activate.
_KERNEL = "xtr-dependency-injection"

_DECLARES_A_BUNDLE = re.compile(r"^@as_bundle\b", re.MULTILINE)
_APPLICATION_HEADING = "## Use in an application"
_BULLET = re.compile(r"^- \*\*(?P<name>[^*]+)\*\*")
_BACKTICKED = re.compile(r"`([^`]+)`")
_ENV_KEY = re.compile(r"[A-Z][A-Z0-9_]*")
# A bullet that opens with "nothing" asks the application for nothing of its own. What it
# goes on to name is what the package reads where a deployment already set it, or what
# another package's recipe writes - neither is this recipe's to declare.
_NOTHING = re.compile("^- \\*\\*[^*]+\\*\\* [-\u2014] nothing\\b", re.IGNORECASE)
# A backticked token is read as a ``.gitignore`` line only when it is anchored at the root
# or carries a glob: a bare path in prose is as often a directory the bullet only points at -
# "whatever directory the file handlers write to, such as `var/log/`" - as a line to write.
_IGNORE_LINE = re.compile(r"^/|\*")


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


def _declares_a_bundle(package_dir: Path) -> bool:
    """Tell whether a module under the package's ``src`` declares a bundle."""
    return any(
        _DECLARES_A_BUNDLE.search(module.read_text(encoding="utf-8"))
        for module in (package_dir / "src").rglob("*.py")
    )


def _recipe_dir(package_dir: Path, recipe_target: str) -> Path:
    """Return the recipe subpackage directory a ``xtr_recipes`` target names."""
    return package_dir.joinpath("src", *recipe_target.split("."))


def _manifest(recipe_dir: Path) -> RecipeConfig:
    """Parse the recipe's ``manifest.toml`` through the library's own parser."""
    with (recipe_dir / "manifest.toml").open("rb") as handle:
        # The parser names the distribution in every error it raises: the package
        # directory, two levels above the import package the recipe lives in.
        return RecipeConfig.from_toml(recipe_dir.parents[2].name, _table(tomllib.load(handle)))


def _manifests(package_dir: Path) -> list[RecipeConfig]:
    """Parse every recipe the package advertises."""
    return [
        _manifest(_recipe_dir(package_dir, target))
        for target in _entry_points(_pyproject(package_dir), _RECIPES_GROUP).values()
    ]


def _application_section(package_dir: Path) -> str:
    """Return the README's *Use in an application* section, heading included."""
    text = (package_dir / "README.md").read_text(encoding="utf-8")
    start = text.index(_APPLICATION_HEADING)
    end = text.find("\n## ", start + len(_APPLICATION_HEADING))
    return text[start:] if end == -1 else text[start:end]


def _bullet(section: str, name: str) -> str:
    """Return the ``**name**`` bullet of a section, its continuation lines included."""
    collected: list[str] = []
    for line in section.splitlines():
        matched = _BULLET.match(line)
        if matched is not None:
            if collected:
                break
            if matched.group("name").strip() == name:
                collected.append(line)
        elif collected:
            if not line.startswith("  "):
                break
            collected.append(line)
    return "\n".join(collected)


def _unanchored(line: str) -> str:
    """Return a ``.gitignore`` line as prose writes it, without the root anchor."""
    return line.lstrip("/")


def _variables_asked_for(bullet: str) -> set[str]:
    """Return the environment variables an *Environment* bullet asks the application to set."""
    if _NOTHING.match(bullet):
        return set()
    return {token for token in _BACKTICKED.findall(bullet) if _ENV_KEY.fullmatch(token)}


def _lines_asked_for(bullet: str) -> set[str]:
    """Return the ``.gitignore`` lines an *Ignore* bullet asks for, each without its anchor."""
    if _NOTHING.match(bullet):
        return set()
    return {
        _unanchored(token) for token in _BACKTICKED.findall(bullet) if _IGNORE_LINE.search(token)
    }


_PACKAGES = sorted(
    (
        path.parent
        for path in _ROOT.glob("packages/*/pyproject.toml")
        if path.parent.name != _KERNEL and _declares_a_bundle(path.parent)
    ),
    key=lambda path: path.name,
)


def _id(package_dir: Path) -> str:
    return package_dir.name


def test_bundle_packages_are_found() -> None:
    assert _PACKAGES


@pytest.mark.parametrize("package_dir", _PACKAGES, ids=_id)
def test_a_declared_bundle_is_advertised_with_a_recipe(package_dir: Path) -> None:
    data = _pyproject(package_dir)

    assert _entry_points(data, _BUNDLES_GROUP), f"{package_dir.name}: no {_BUNDLES_GROUP} entry"
    assert _entry_points(data, _RECIPES_GROUP), f"{package_dir.name}: no {_RECIPES_GROUP} entry"


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


@pytest.mark.parametrize("package_dir", _PACKAGES, ids=_id)
def test_the_readme_names_what_the_recipe_writes(package_dir: Path) -> None:
    section = _application_section(package_dir)

    unnamed: list[str] = []
    for config in _manifests(package_dir):
        unnamed += [key for key in config.env if key not in section]
        unnamed += [destination for destination in config.files if destination not in section]
        unnamed += [
            line
            for line in config.gitignore
            if line not in section and _unanchored(line) not in section
        ]

    assert unnamed == [], f"{package_dir.name}: {_APPLICATION_HEADING} does not name {unnamed}"


@pytest.mark.parametrize("package_dir", _PACKAGES, ids=_id)
def test_the_recipe_writes_the_variables_the_environment_bullet_asks_for(
    package_dir: Path,
) -> None:
    declared = {key for config in _manifests(package_dir) for key in config.env}

    asked = _variables_asked_for(_bullet(_application_section(package_dir), "Environment"))

    assert asked <= declared, f"{package_dir.name}: no [env] entry for {sorted(asked - declared)}"


@pytest.mark.parametrize("package_dir", _PACKAGES, ids=_id)
def test_the_recipe_writes_the_lines_the_ignore_bullet_asks_for(package_dir: Path) -> None:
    declared = {
        _unanchored(line) for config in _manifests(package_dir) for line in config.gitignore
    }

    asked = _lines_asked_for(_bullet(_application_section(package_dir), "Ignore"))

    assert asked <= declared, (
        f"{package_dir.name}: no [gitignore] line for {sorted(asked - declared)}"
    )


_SAMPLE_SECTION = """## Use in an application

- **Install** \u2014 `uv add xtr-thing`.
- **Environment** \u2014 `THING_URL`, read when the thing is built; and
  `THING_TOKEN`, the token it signs with.
- **Ignore** \u2014 `/var/thing/`: where it writes, and `kernel.share_dir` under it.
- **Check** \u2014 `debug:bundles`.
"""


def test_a_bullet_is_read_with_its_continuation_lines() -> None:
    assert "THING_TOKEN" in _bullet(_SAMPLE_SECTION, "Environment")


def test_a_manifest_that_cannot_be_read_is_reported_against_its_distribution(
    tmp_path: Path,
) -> None:
    recipe_dir = tmp_path / "xtr-thing" / "src" / "xtr_thing" / "recipe"
    recipe_dir.mkdir(parents=True)
    _ = (recipe_dir / "manifest.toml").write_text("[nonsense]\n", encoding="utf-8")

    with pytest.raises(InvalidManifestError, match="recipe 'xtr-thing'"):
        _ = _manifest(recipe_dir)


def test_the_variables_a_bullet_asks_for_are_the_ones_it_names() -> None:
    bullet = _bullet(_SAMPLE_SECTION, "Environment")

    assert _variables_asked_for(bullet) == {"THING_URL", "THING_TOKEN"}


def test_a_bullet_opening_with_nothing_asks_for_nothing() -> None:
    bullet = "- **Environment** \u2014 nothing required; `SHELL_VERBOSITY` sets the verbosity."

    assert _variables_asked_for(bullet) == set()


def test_the_lines_a_bullet_asks_for_lose_their_anchor_and_leave_prose_alone() -> None:
    bullet = _bullet(_SAMPLE_SECTION, "Ignore")

    assert _lines_asked_for(bullet) == {"var/thing/"}
