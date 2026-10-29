from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.support import write_package
from xtr_recipes.exception import ProjectNotFoundError, UnreadableFileError
from xtr_recipes.project import Project

if TYPE_CHECKING:
    from pathlib import Path

_DEPENDENCIES = """\
[project]
name = "app"
dependencies = [
  "fastapi>=0.121.3",
  "xtr-messenger[redis,taskiq]",
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

_DEV_GROUP = """\
[project]
name = "app"

[dependency-groups]
dev = ["Ruff>=0.8", "xtr_maker[orm] ; python_version >= '3.11'"]
"""

_LEGACY_DEV = """\
[project]
name = "app"

[tool.uv]
dev-dependencies = ["pytest>=8"]
"""

_BOTH_DEV_LISTS = """\
[project]
name = "app"

[dependency-groups]
dev = ["ruff", "xtr-maker"]

[tool.uv]
dev-dependencies = ["pytest", "Ruff"]
"""

_ALSO_AT_RUNTIME = """\
[project]
name = "app"
dependencies = ["xtr-maker"]

[dependency-groups]
dev = ["xtr_maker", "ruff"]
"""

_INCLUDED_GROUP = """\
[project]
name = "app"

[dependency-groups]
dev = [{include-group = "lint"}, "xtr-maker"]
lint = ["ruff"]
"""

_OTHER_GROUP = """\
[project]
name = "app"

[dependency-groups]
test = ["pytest"]
"""

_MALFORMED_DEV_LISTS = {
    "groups not a table": 'dependency-groups = "oops"\n\n[project]\nname = "app"\n',
    "dev not a list": '[project]\nname = "app"\n\n[dependency-groups]\ndev = "oops"\n',
    "no string in dev": '[project]\nname = "app"\n\n[dependency-groups]\ndev = [1, true]\n',
    "uv not a table": '[project]\nname = "app"\n\n[tool]\nuv = "oops"\n',
    "legacy not a list": '[project]\nname = "app"\n\n[tool.uv]\ndev-dependencies = "oops"\n',
}


def _write(directory: Path, body: str) -> None:
    _ = (directory / "pyproject.toml").write_text(body, encoding="utf-8")


def _load(directory: Path, body: str) -> Project:
    _write(directory, body)
    _ = write_package(directory / "src", "app")
    return Project.load(directory)


def test_the_app_is_the_package_holding_the_kernel(tmp_path: Path) -> None:
    _write(tmp_path, '[project]\nname = "distribution-name"\n')
    package = write_package(tmp_path / "src", "shop")

    project = Project.load(tmp_path)

    assert project.app == "shop"
    assert project.package_dir == package
    assert project.project_dir == tmp_path


def test_a_nested_application_package_is_named_by_its_dotted_path(tmp_path: Path) -> None:
    _write(tmp_path, '[project]\nname = "acme-shop"\n')
    package = write_package(tmp_path / "src", "acme.shop")

    project = Project.load(tmp_path)

    assert project.app == "acme.shop"
    assert project.package_dir == package


def test_a_manifest_with_no_project_table_is_read(tmp_path: Path) -> None:
    project = _load(tmp_path, "[tool.other]\nkey = 1\n")

    assert project.app == "app"
    assert project.dependencies == ()
    assert project.script is None


def test_load_raises_when_no_package_holds_a_kernel(tmp_path: Path) -> None:
    _write(tmp_path, '[project]\nname = "app"\n')
    _ = write_package(tmp_path / "src", "app", kernel=False)

    with pytest.raises(ProjectNotFoundError) as exc:
        _ = Project.load(tmp_path)

    assert "kernel.py" in exc.value.reason


def test_it_reads_direct_dependencies_stripped_and_normalised(tmp_path: Path) -> None:
    assert _load(tmp_path, _DEPENDENCIES).dependencies == (
        "fastapi",
        "xtr-messenger",
        "xtr-security-jwt",
        "pkg",
    )


def test_it_returns_no_dependencies_when_the_list_is_malformed(tmp_path: Path) -> None:
    assert _load(tmp_path, '[project]\nname = "app"\ndependencies = "oops"\n').dependencies == ()


def test_it_skips_a_non_string_dependency_entry(tmp_path: Path) -> None:
    body = '[project]\nname = "app"\ndependencies = [1, "xtr-foo"]\n'

    assert _load(tmp_path, body).dependencies == ("xtr-foo",)


def test_it_reads_the_dev_group_stripped_and_normalised(tmp_path: Path) -> None:
    assert _load(tmp_path, _DEV_GROUP).dev_dependencies == ("ruff", "xtr-maker")


def test_it_reads_the_dev_dependencies_uv_listed_before_dependency_groups(tmp_path: Path) -> None:
    assert _load(tmp_path, _LEGACY_DEV).dev_dependencies == ("pytest",)


def test_it_reads_both_dev_lists_each_name_once_in_order(tmp_path: Path) -> None:
    assert _load(tmp_path, _BOTH_DEV_LISTS).dev_dependencies == ("ruff", "xtr-maker", "pytest")


def test_a_runtime_dependency_is_not_also_a_dev_dependency(tmp_path: Path) -> None:
    project = _load(tmp_path, _ALSO_AT_RUNTIME)

    assert project.dependencies == ("xtr-maker",)
    assert project.dev_dependencies == ("ruff",)


def test_it_does_not_follow_a_group_the_dev_group_includes(tmp_path: Path) -> None:
    assert _load(tmp_path, _INCLUDED_GROUP).dev_dependencies == ("xtr-maker",)


def test_another_dependency_group_holds_no_dev_dependency(tmp_path: Path) -> None:
    assert _load(tmp_path, _OTHER_GROUP).dev_dependencies == ()


@pytest.mark.parametrize("body", _MALFORMED_DEV_LISTS.values(), ids=_MALFORMED_DEV_LISTS.keys())
def test_it_returns_no_dev_dependencies_when_a_dev_list_is_malformed(
    tmp_path: Path,
    body: str,
) -> None:
    assert _load(tmp_path, body).dev_dependencies == ()


def test_it_reads_the_first_script_name(tmp_path: Path) -> None:
    assert _load(tmp_path, _SCRIPTS).script == "app"


def test_the_script_is_none_when_there_is_no_scripts_table(tmp_path: Path) -> None:
    assert _load(tmp_path, '[project]\nname = "app"\n').script is None


def test_the_script_is_none_when_the_scripts_table_is_empty(tmp_path: Path) -> None:
    assert _load(tmp_path, '[project]\nname = "app"\n\n[project.scripts]\n').script is None


def test_load_raises_naming_the_missing_manifest(tmp_path: Path) -> None:
    with pytest.raises(ProjectNotFoundError) as exc:
        _ = Project.load(tmp_path)

    assert exc.value.directory == tmp_path
    assert "pyproject.toml" in exc.value.reason


def test_discover_finds_the_nearest_project_upward(tmp_path: Path) -> None:
    _ = _load(tmp_path, '[project]\nname = "app"\n')
    nested = tmp_path / "src" / "app" / "deep"
    nested.mkdir()

    project = Project.discover(nested)

    assert project.project_dir == tmp_path
    assert project.app == "app"


def test_discover_defaults_to_the_current_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _ = _load(tmp_path, '[project]\nname = "app"\n')
    monkeypatch.chdir(tmp_path)

    assert Project.discover().app == "app"


def test_discover_raises_when_no_project_is_found(tmp_path: Path) -> None:
    # The filesystem root: nothing above it, and nothing is written there.
    with pytest.raises(ProjectNotFoundError) as exc:
        _ = Project.discover(tmp_path.parents[-1])

    assert "pyproject.toml" in exc.value.reason


def test_it_names_the_manifest_when_it_is_not_valid_toml(tmp_path: Path) -> None:
    _ = (tmp_path / "pyproject.toml").write_text("not = = toml", encoding="utf-8")

    with pytest.raises(UnreadableFileError) as exc:
        _ = Project.load(tmp_path)

    assert exc.value.path == tmp_path / "pyproject.toml"
