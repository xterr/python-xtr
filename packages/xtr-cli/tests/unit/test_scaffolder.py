from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

import pytest

from tests.support import RecordingRunner, build_settings
from xtr_cli import DirectoryNotEmptyError, Scaffolder, StepFailedError, Template

if TYPE_CHECKING:
    from pathlib import Path


def _scaffolder(runner: RecordingRunner | None = None, version: str = "3.0.0") -> Scaffolder:
    return Scaffolder(runner if runner is not None else RecordingRunner(), version)


def test_the_xtr_requirements_are_pinned_to_the_tools_major(tmp_path: Path) -> None:
    plan = _scaffolder().plan(build_settings(tmp_path / "shop"))

    assert plan.commands[0] == (
        "uv",
        "add",
        "--",
        "xtr-dependency-injection>=3.0,<4",
        "xtr-console>=3.0,<4",
        "xtr-dotenv>=3.0,<4",
    )


def test_a_requirement_with_extras_is_pinned_and_a_third_party_one_is_left_alone(
    tmp_path: Path,
) -> None:
    plan = _scaffolder().plan(build_settings(tmp_path / "shop", template="webapp"))

    assert "xtr-orm[postgres]>=3.0,<4" in plan.commands[0]
    assert "fastapi" in plan.commands[0]


def test_the_tools_are_added_as_development_dependencies_then_the_recipes_applied(
    tmp_path: Path,
) -> None:
    plan = _scaffolder().plan(build_settings(tmp_path / "shop"))

    assert plan.commands[1:] == (
        ("uv", "add", "--dev", "--", "xtr-recipes>=3.0,<4", "pytest", "ruff", "basedpyright", "ty"),
        ("uv", "run", "xtr-recipes", "recipes:sync"),
        ("git", "init", "--quiet"),
    )


def test_a_development_version_pins_nothing(tmp_path: Path) -> None:
    plan = _scaffolder(version="0+unknown").plan(build_settings(tmp_path / "shop"))

    assert "xtr-console" in plan.commands[0]


def test_a_template_without_requirements_runs_only_git(tmp_path: Path) -> None:
    bare = Template("bare", "", (), (), (), ())

    plan = _scaffolder().plan(replace(build_settings(tmp_path / "shop"), template=bare))

    assert plan.commands == (("git", "init", "--quiet"),)


def test_no_git_and_an_existing_repository_leave_git_out(tmp_path: Path) -> None:
    (tmp_path / "kept" / ".git").mkdir(parents=True)

    without = _scaffolder().plan(build_settings(tmp_path / "shop", git=False))
    kept = _scaffolder().plan(build_settings(tmp_path / "kept"))

    assert all(argv[0] != "git" for argv in (*without.commands, *kept.commands))


def test_local_packages_are_listed_as_editable_sources(tmp_path: Path) -> None:
    (tmp_path / "packages" / "xtr-console").mkdir(parents=True)
    _ = (tmp_path / "packages" / "xtr-console" / "pyproject.toml").write_text("", encoding="utf-8")
    (tmp_path / "packages" / "not-a-package").mkdir()

    plan = _scaffolder().plan(
        build_settings(tmp_path / "shop", local_packages=tmp_path / "packages")
    )
    pyproject = dict(plan.files)["pyproject.toml"]
    source = (tmp_path / "packages" / "xtr-console").as_posix()

    assert pyproject.endswith(
        f'\n[tool.uv.sources]\nxtr-console = {{ path = "{source}", editable = true }}\n'
    )
    assert "not-a-package" not in pyproject


def test_applying_writes_the_files_and_runs_the_commands_in_the_project(tmp_path: Path) -> None:
    runner = RecordingRunner()
    scaffolder = _scaffolder(runner)
    plan = scaffolder.plan(build_settings(tmp_path / "shop"))
    reported: list[str] = []

    scaffolder.apply(plan, reported.append)

    assert (tmp_path / "shop" / "src" / "shop" / "kernel.py").is_file()
    assert [argv for argv, _ in runner.calls] == list(plan.commands)
    assert {cwd for _, cwd in runner.calls} == {tmp_path / "shop"}
    assert reported == list(plan.render())


def test_a_failing_command_stops_the_run_and_keeps_what_was_made(tmp_path: Path) -> None:
    runner = RecordingRunner((0, 2))
    scaffolder = _scaffolder(runner)
    plan = scaffolder.plan(build_settings(tmp_path / "shop"))

    with pytest.raises(StepFailedError) as raised:
        scaffolder.apply(plan, lambda _: None)

    assert raised.value.argv == plan.commands[1]
    assert raised.value.code == 2
    assert len(runner.calls) == 2
    assert (tmp_path / "shop" / "pyproject.toml").is_file()


def test_a_missing_directory_or_one_holding_only_metadata_is_empty(tmp_path: Path) -> None:
    (tmp_path / "metadata" / ".git").mkdir(parents=True)
    (tmp_path / "metadata" / ".idea").mkdir()

    Scaffolder.check_directory(tmp_path / "missing")
    Scaffolder.check_directory(tmp_path / "metadata")


def test_a_directory_holding_files_is_refused(tmp_path: Path) -> None:
    _ = (tmp_path / "README.md").write_text("", encoding="utf-8")
    (tmp_path / ".git").mkdir()

    with pytest.raises(DirectoryNotEmptyError) as raised:
        Scaffolder.check_directory(tmp_path)

    assert raised.value.found == ("README.md",)


def test_a_file_in_place_of_the_directory_is_refused(tmp_path: Path) -> None:
    _ = (tmp_path / "shop").write_text("", encoding="utf-8")

    with pytest.raises(DirectoryNotEmptyError):
        Scaffolder.check_directory(tmp_path / "shop")
