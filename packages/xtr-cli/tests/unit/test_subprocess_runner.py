from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from xtr_cli import ProcessRunnerInterface, SubprocessRunner
from xtr_cli.subprocess_runner import NOT_FOUND

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_it_is_a_process_runner() -> None:
    assert isinstance(SubprocessRunner(), ProcessRunnerInterface)


def test_it_returns_the_exit_code_of_the_command_run_where_asked(tmp_path: Path) -> None:
    script = "import pathlib, sys; pathlib.Path('ran').touch(); sys.exit(3)"

    assert SubprocessRunner().run((sys.executable, "-c", script), tmp_path) == 3
    assert (tmp_path / "ran").is_file()


def test_a_command_not_on_the_path_ends_as_a_shell_reports_it(tmp_path: Path) -> None:
    assert SubprocessRunner().run(("xtr-cli-no-such-program",), tmp_path) == NOT_FOUND


def test_the_active_virtual_environment_is_not_passed_on(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("VIRTUAL_ENV", "/somewhere/.venv")
    script = "import os, sys; sys.exit(0 if 'VIRTUAL_ENV' not in os.environ else 1)"

    assert SubprocessRunner().run((sys.executable, "-c", script), tmp_path) == 0
