from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from xtr_recipes.exception import ProjectNotFoundError, UnreadableFileError
from xtr_recipes.project import Project

if TYPE_CHECKING:
    from pathlib import Path

_DEPENDENCIES = """\
[project]
name = "app"
dependencies = [
  "fastapi>=0.121.3",
  "xtr-messenger[di,console]",
  "xtr_security_jwt == 2.0 ; python_version >= '3.11'",
  "pkg @ https://example.test/pkg.whl",
  "xtr-messenger",
]
"""

_SCRIPTS = """\
[project]
name = "app"

[project.scripts]
app = "app.__main__:main"
app-web = "app.web:main"
"""


def _write(directory: Path, body: str) -> None:
    _ = (directory / "pyproject.toml").write_text(body, encoding="utf-8")


def test_load_resolves_the_app_from_the_project_name(tmp_path: Path) -> None:
    _write(tmp_path, '[project]\nname = "my-app"\n')
    (tmp_path / "src" / "my_app").mkdir(parents=True)

    project = Project.load(tmp_path)

    assert project.app == "my_app"
    assert project.project_dir == tmp_path


def test_load_resolves_a_flat_layout_app(tmp_path: Path) -> None:
    _write(tmp_path, '[project]\nname = "flat"\n')
    (tmp_path / "flat").mkdir()

    assert Project.load(tmp_path).app == "flat"


def test_the_package_dir_is_the_src_layout_package(tmp_path: Path) -> None:
    _write(tmp_path, '[project]\nname = "my-app"\n')
    (tmp_path / "src" / "my_app").mkdir(parents=True)

    assert Project.load(tmp_path).package_dir == tmp_path / "src" / "my_app"


def test_the_package_dir_is_the_flat_layout_package(tmp_path: Path) -> None:
    _write(tmp_path, '[project]\nname = "flat"\n')
    (tmp_path / "flat").mkdir()

    assert Project.load(tmp_path).package_dir == tmp_path / "flat"


def test_the_package_dir_of_a_package_that_is_gone_is_at_the_project_root(tmp_path: Path) -> None:
    project = Project(project_dir=tmp_path, app="ghost", dependencies=(), script=None)

    assert project.package_dir == tmp_path / "ghost"


def test_the_app_setting_overrides_the_project_name(tmp_path: Path) -> None:
    _write(tmp_path, '[project]\nname = "dist-name"\n\n[tool.xtr-recipes]\napp = "custom"\n')
    (tmp_path / "src" / "custom").mkdir(parents=True)

    assert Project.load(tmp_path).app == "custom"


def test_it_falls_back_to_the_name_when_the_app_setting_is_not_a_string(tmp_path: Path) -> None:
    _write(tmp_path, '[project]\nname = "app"\n\n[tool.xtr-recipes]\napp = 123\n')
    (tmp_path / "src" / "app").mkdir(parents=True)

    assert Project.load(tmp_path).app == "app"


def test_it_ignores_a_tool_table_without_the_app_setting(tmp_path: Path) -> None:
    _write(tmp_path, '[project]\nname = "app"\n\n[tool.other]\nkey = 1\n')
    (tmp_path / "src" / "app").mkdir(parents=True)

    assert Project.load(tmp_path).app == "app"


def test_it_reads_a_project_configured_only_by_the_app_setting(tmp_path: Path) -> None:
    _write(tmp_path, '[tool.xtr-recipes]\napp = "app"\n')
    (tmp_path / "src" / "app").mkdir(parents=True)

    project = Project.load(tmp_path)

    assert project.app == "app"
    assert project.dependencies == ()
    assert project.script is None


def test_it_reads_direct_dependencies_stripped_and_normalised(tmp_path: Path) -> None:
    _write(tmp_path, _DEPENDENCIES)
    (tmp_path / "src" / "app").mkdir(parents=True)

    assert Project.load(tmp_path).dependencies == (
        "fastapi",
        "xtr-messenger",
        "xtr-security-jwt",
        "pkg",
    )


def test_it_returns_no_dependencies_when_the_list_is_malformed(tmp_path: Path) -> None:
    _write(tmp_path, '[project]\nname = "app"\ndependencies = "oops"\n')
    (tmp_path / "src" / "app").mkdir(parents=True)

    assert Project.load(tmp_path).dependencies == ()


def test_it_skips_a_non_string_dependency_entry(tmp_path: Path) -> None:
    _write(tmp_path, '[project]\nname = "app"\ndependencies = [1, "xtr-foo"]\n')
    (tmp_path / "src" / "app").mkdir(parents=True)

    assert Project.load(tmp_path).dependencies == ("xtr-foo",)


def test_it_reads_the_first_script_name(tmp_path: Path) -> None:
    _write(tmp_path, _SCRIPTS)
    (tmp_path / "src" / "app").mkdir(parents=True)

    assert Project.load(tmp_path).script == "app"


def test_the_script_is_none_when_there_is_no_scripts_table(tmp_path: Path) -> None:
    _write(tmp_path, '[project]\nname = "app"\n')
    (tmp_path / "src" / "app").mkdir(parents=True)

    assert Project.load(tmp_path).script is None


def test_the_script_is_none_when_the_scripts_table_is_empty(tmp_path: Path) -> None:
    _write(tmp_path, '[project]\nname = "app"\n\n[project.scripts]\n')
    (tmp_path / "src" / "app").mkdir(parents=True)

    assert Project.load(tmp_path).script is None


def test_load_raises_naming_the_project_name_when_the_package_is_missing(tmp_path: Path) -> None:
    _write(tmp_path, '[project]\nname = "ghost"\n')

    with pytest.raises(ProjectNotFoundError) as exc:
        _ = Project.load(tmp_path)

    assert exc.value.setting == "[project].name"
    assert exc.value.directory == tmp_path


def test_load_raises_naming_the_app_setting_when_the_override_is_missing(tmp_path: Path) -> None:
    _write(tmp_path, '[project]\nname = "x"\n\n[tool.xtr-recipes]\napp = "ghost"\n')

    with pytest.raises(ProjectNotFoundError) as exc:
        _ = Project.load(tmp_path)

    assert exc.value.setting == "[tool.xtr-recipes] app"


def test_load_raises_when_neither_the_app_setting_nor_the_name_is_present(tmp_path: Path) -> None:
    _write(tmp_path, "[tool.other]\nkey = 1\n")

    with pytest.raises(ProjectNotFoundError) as exc:
        _ = Project.load(tmp_path)

    assert exc.value.setting == "[project].name"


def test_load_raises_naming_the_missing_manifest(tmp_path: Path) -> None:
    with pytest.raises(ProjectNotFoundError) as exc:
        _ = Project.load(tmp_path)

    assert exc.value.setting is None
    assert exc.value.directory == tmp_path
    assert "pyproject.toml" in exc.value.reason


def test_discover_finds_the_nearest_project_upward(tmp_path: Path) -> None:
    _write(tmp_path, '[project]\nname = "app"\n')
    (tmp_path / "src" / "app").mkdir(parents=True)
    nested = tmp_path / "src" / "app" / "deep"
    nested.mkdir()

    project = Project.discover(nested)

    assert project.project_dir == tmp_path
    assert project.app == "app"


def test_discover_defaults_to_the_current_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write(tmp_path, '[project]\nname = "app"\n')
    (tmp_path / "src" / "app").mkdir(parents=True)
    monkeypatch.chdir(tmp_path)

    assert Project.discover().app == "app"


def test_discover_raises_when_no_project_is_found(tmp_path: Path) -> None:
    # The filesystem root: nothing above it, and nothing is written there.
    with pytest.raises(ProjectNotFoundError) as exc:
        _ = Project.discover(tmp_path.parents[-1])

    assert exc.value.setting is None


def test_it_names_the_manifest_when_it_is_not_valid_toml(tmp_path: Path) -> None:
    _ = (tmp_path / "pyproject.toml").write_text("not = = toml", encoding="utf-8")

    with pytest.raises(UnreadableFileError) as exc:
        _ = Project.load(tmp_path)

    assert exc.value.path == tmp_path / "pyproject.toml"
