from __future__ import annotations

import sys
from typing import TYPE_CHECKING, final

import pytest

from xtr_recipes import entry_point_recipe_source as eps
from xtr_recipes.entry_point_recipe_source import EntryPointRecipeSource, read_recipe_content
from xtr_recipes.exception import InvalidManifestError

if TYPE_CHECKING:
    from pathlib import Path


@final
class _Dist:
    name = "Xtr-Messenger"


@final
class _Entry:
    module = "listed_package.recipe"
    dist = _Dist()


@final
class _NoDistEntry:
    module = "ignored"
    dist = None


def _no_entries(group: str) -> list[object]:
    assert group == "xtr_recipes"
    return []


def test_load_returns_a_mapping_when_nothing_advertises_a_recipe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(eps, "entry_points", _no_entries)

    assert EntryPointRecipeSource().load() == {}


def test_load_reads_each_distributions_recipe_normalising_its_name(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recipe = tmp_path / "listed_package" / "recipe"
    recipe.mkdir(parents=True)
    _ = (recipe / "manifest.toml").write_bytes(b"[bundles]\n")
    monkeypatch.setattr(sys, "path", [str(tmp_path), *sys.path])

    def entries(group: str) -> list[object]:
        assert group == "xtr_recipes"
        return [_Entry(), _NoDistEntry()]

    monkeypatch.setattr(eps, "entry_points", entries)

    recipes = EntryPointRecipeSource().load()

    assert set(recipes) == {"xtr-messenger"}
    assert recipes["xtr-messenger"].manifest == b"[bundles]\n"


def test_read_recipe_content_reads_the_manifest_and_nested_templates(tmp_path: Path) -> None:
    _ = (tmp_path / "manifest.toml").write_bytes(b"[bundles]\n")
    config_dir = tmp_path / "files" / "config"
    config_dir.mkdir(parents=True)
    _ = (config_dir / "messenger.py.tmpl").write_bytes(b"MESSENGER = ${app}\n")

    content = read_recipe_content(tmp_path)

    assert content.manifest == b"[bundles]\n"
    assert content.templates == {"files/config/messenger.py.tmpl": b"MESSENGER = ${app}\n"}


def test_read_recipe_content_skips_the_manifest_among_the_templates(tmp_path: Path) -> None:
    _ = (tmp_path / "manifest.toml").write_bytes(b"[env]\n")
    _ = (tmp_path / "notes.txt").write_bytes(b"hello")

    content = read_recipe_content(tmp_path)

    assert content.templates == {"notes.txt": b"hello"}


def test_read_recipe_content_ignores_compiled_bytecode(tmp_path: Path) -> None:
    _ = (tmp_path / "manifest.toml").write_bytes(b"[env]\n")
    cache = tmp_path / "__pycache__"
    cache.mkdir()
    _ = (cache / "__init__.cpython-313.pyc").write_bytes(b"\x00compiled")

    content = read_recipe_content(tmp_path)

    assert content.templates == {}


@final
class _BrokenEntry:
    module = "broken_package.recipe"
    dist = _Dist()


def test_load_reads_a_recipe_without_importing_its_package(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package = tmp_path / "broken_package"
    (package / "recipe").mkdir(parents=True)
    _ = (package / "__init__.py").write_text("raise ImportError('broken')\n", encoding="utf-8")
    _ = (package / "recipe" / "manifest.toml").write_bytes(b"[bundles]\n")
    monkeypatch.setattr(sys, "path", [str(tmp_path), *sys.path])

    def entries(group: str) -> list[object]:
        assert group == "xtr_recipes"
        return [_BrokenEntry()]

    monkeypatch.setattr(eps, "entry_points", entries)

    assert EntryPointRecipeSource().load()["xtr-messenger"].manifest == b"[bundles]\n"


@final
class _MissingEntry:
    module = "no_such_installed_package.recipe"
    dist = _Dist()


def test_load_names_an_entry_point_whose_package_is_not_installed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def entries(group: str) -> list[object]:
        assert group == "xtr_recipes"
        return [_MissingEntry()]

    monkeypatch.setattr(eps, "entry_points", entries)

    with pytest.raises(InvalidManifestError, match="no_such_installed_package"):
        _ = EntryPointRecipeSource().load()
