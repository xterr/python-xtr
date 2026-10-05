from __future__ import annotations

import sys
from io import StringIO
from typing import TYPE_CHECKING

import pytest
from xtr_console import ConsoleStyle, ExitCode

from tests.support import build_project
from xtr_recipes import command_support
from xtr_recipes.exception import ProjectNotFoundError, RecipeNotInstalledError
from xtr_recipes.operation.plan import Plan
from xtr_recipes.operation.write_lock import WriteLock
from xtr_recipes.recipe_lock import RecipeLock
from xtr_recipes.synchronizer import Synchronizer

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

_MARKUP = "skipped: install xtr-security[di]"


@pytest.fixture
def output() -> StringIO:
    return StringIO()


@pytest.fixture
def io(output: StringIO) -> ConsoleStyle:
    return ConsoleStyle(output, StringIO(), width=100, decorated=False, interactive=False)


def test_load_project_loads_the_directory_it_is_given(tmp_path: Path) -> None:
    expected = build_project(tmp_path)

    assert command_support.load_project(tmp_path) == expected


def test_load_project_discovers_the_one_around_the_current_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = build_project(tmp_path)
    monkeypatch.chdir(tmp_path / "src")

    assert command_support.load_project(None) == expected


def test_load_project_refuses_a_directory_with_no_application(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _ = (tmp_path / "pyproject.toml").write_text('[project]\nname = "absent"\n', encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ProjectNotFoundError):
        _ = command_support.load_project(None)


def test_build_synchronizer_returns_one_for_the_project(tmp_path: Path) -> None:
    project = build_project(tmp_path)

    assert isinstance(command_support.build_synchronizer(project), Synchronizer)


def test_run_returns_the_exit_code_of_the_process(tmp_path: Path) -> None:
    argv: Sequence[str] = (sys.executable, "-c", "raise SystemExit(3)")

    assert command_support.run(argv, tmp_path) == 3


def test_run_runs_the_process_in_the_directory_it_is_given(tmp_path: Path) -> None:
    argv: Sequence[str] = (sys.executable, "-c", "open('here.txt', 'w').close()")

    _ = command_support.run(argv, tmp_path)

    assert (tmp_path / "here.txt").is_file()


def test_report_says_there_is_nothing_to_do_for_an_empty_plan(
    io: ConsoleStyle,
    output: StringIO,
) -> None:
    command_support.report(io, Plan())

    assert output.getvalue() == "nothing to do\n"


def test_report_prints_every_step_of_a_plan(
    io: ConsoleStyle,
    output: StringIO,
    tmp_path: Path,
) -> None:
    plan = Plan((WriteLock(RecipeLock(), tmp_path),))

    command_support.report(io, plan)

    assert output.getvalue() == "write xtr.lock\n"


def test_write_keeps_a_bracketed_word_from_reading_as_markup(
    io: ConsoleStyle,
    output: StringIO,
) -> None:
    command_support.write(io, (_MARKUP,))

    assert output.getvalue() == f"{_MARKUP}\n"


def test_failed_reports_the_message_and_fails(io: ConsoleStyle, output: StringIO) -> None:
    code = command_support.failed(io, RecipeNotInstalledError("xtr-nothing"))

    assert code == ExitCode.FAILURE
    assert "xtr-nothing has no recipe to apply" in output.getvalue()


@pytest.mark.parametrize(
    ("spelled", "normalised"),
    [
        ("xtr-messenger", "xtr-messenger"),
        ("XTR_Messenger", "xtr-messenger"),
        ("xtr.messenger", "xtr-messenger"),
        ("  xtr__messenger  ", "xtr-messenger"),
    ],
)
def test_normalise_spells_a_name_as_a_dependency_list_does(
    spelled: str,
    normalised: str,
) -> None:
    assert command_support.normalise(spelled) == normalised


def test_change_dependency_syncs_in_a_fresh_process_after_the_change(
    io: ConsoleStyle,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = build_project(tmp_path)
    calls: list[tuple[tuple[str, ...], Path]] = []

    def record(argv: Sequence[str], cwd: Path) -> int:
        calls.append((tuple(argv), cwd))
        return 0

    monkeypatch.setattr(command_support, "run", record)

    code = command_support.change_dependency(io, project, ("uv", "add", "xtr-clock"))

    assert code == ExitCode.SUCCESS
    assert calls[1] == (
        ("uv", "run", "xtr-recipes", "recipes:sync", "--project-dir", str(tmp_path)),
        tmp_path,
    )


def test_change_dependency_does_not_sync_when_the_change_failed(
    io: ConsoleStyle,
    output: StringIO,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = build_project(tmp_path)
    calls: list[tuple[str, ...]] = []

    def record(argv: Sequence[str], _cwd: Path) -> int:
        calls.append(tuple(argv))
        return 2

    monkeypatch.setattr(command_support, "run", record)

    code = command_support.change_dependency(io, project, ("uv", "add", "xtr-clock[di]"))

    assert code == ExitCode.FAILURE
    assert calls == [("uv", "add", "xtr-clock[di]")]
    assert "uv add xtr-clock[di] failed" in output.getvalue()
