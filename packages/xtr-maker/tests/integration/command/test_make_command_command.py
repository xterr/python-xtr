"""``make:command`` in an application: written through its console, then run by it."""

from __future__ import annotations

import subprocess
import sys
from typing import TYPE_CHECKING, cast

import pytest
from xtr_console import ExitCode

from tests.support.temporary_app import TemporaryApp

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

pytestmark = pytest.mark.anyio

_COLOR = '''"""Colours for the generated command to take."""

from __future__ import annotations

from enum import Enum


class Color(Enum):
    RED = "red"
    GREEN = "green"
'''

_RUFF_IGNORED = "CPY001,D203,D213,COM812,ISC001"
"""What an application selecting every rule turns off: no copyright header, the formatter's
conflicts, and one of each pair of docstring conventions that exclude each other."""


@pytest.fixture
def app(tmp_path: Path) -> Iterator[TemporaryApp]:
    with TemporaryApp(tmp_path, modules={"service.color": _COLOR}) as app:
        yield app


async def _make_report(app: TemporaryApp, name: str) -> None:
    """Write the command ``name``; each test picks its own, as every command module
    imported also declares its name in the process-wide registry."""
    code, output = await app.run(
        [
            "make:command",
            name,
            "--argument",
            "recipient",
            "--argument",
            f"color:{app.package}.service.color.Color",
            "--argument",
            "cc?:list",
            "--option",
            "dry-run",
            "--option",
            "limit:int",
            "-n",
        ]
    )
    assert code == ExitCode.SUCCESS, output


async def test_the_written_command_runs_with_its_arguments_and_options(app: TemporaryApp) -> None:
    await _make_report(app, "app:send-report")
    module = app.import_generated("command.send_report_command")

    code, output = await app.run(
        ["app:send-report", "ada", "green", "bob", "eve", "--dry-run", "--limit", "3"]
    )

    assert code == ExitCode.SUCCESS, output
    assert cast("list[str]", module.__all__) == ["SendReportCommand"]
    assert "recipient='ada'" in output
    assert "color=<Color.GREEN: 'green'>" in output
    assert "cc=['bob', 'eve']" in output
    assert "dry_run=True" in output
    assert "limit=3" in output
    assert "[OK] app:send-report ran." in output


async def test_left_out_values_take_their_defaults(app: TemporaryApp) -> None:
    await _make_report(app, "app:send-defaults")

    code, output = await app.run(["app:send-defaults", "ada", "red"])

    assert code == ExitCode.SUCCESS, output
    assert "cc=None" in output
    assert "dry_run=False" in output
    assert "limit=None" in output


async def test_the_help_lists_every_parameter_with_its_help_text(app: TemporaryApp) -> None:
    await _make_report(app, "app:send-help")

    code, output = await app.run(["app:send-help", "--help"])

    assert code == ExitCode.SUCCESS, output
    assert "Describe what app:send-help does." in output
    for shown in ("RECIPIENT", "Recipient.", "COLOR", "red, green", "CC", "--dry-run", "--limit"):
        assert shown in output


async def test_answers_write_a_command_the_application_lists(app: TemporaryApp) -> None:
    code, output = await app.run(
        ["make:command"],
        inputs=["app:greet", "Greet someone.", "who", "str", "Who to greet.", "y", "", "", ""],
    )
    assert code == ExitCode.SUCCESS, output

    _, listed = await app.run(["list"])

    assert "app:greet" in listed
    assert "Greet someone." in listed


async def test_a_name_already_registered_is_refused(app: TemporaryApp) -> None:
    code, output = await app.run(["make:command", "debug:bundles", "-n"])

    assert code == ExitCode.INVALID
    assert "The command 'debug:bundles' already answers to 'debug:bundles'." in output


async def test_the_maker_is_listed_with_the_console_alone(app: TemporaryApp) -> None:
    _, listed = await app.run(["list"])

    assert "make:command" in listed


async def test_the_generated_file_passes_every_lint_rule_and_the_formatter(
    app: TemporaryApp,
) -> None:
    await _make_report(app, "app:send-lint")
    path = str(app.package_dir / "command" / "send_lint_command.py")

    checked = _ruff(app, "check", "--select", "ALL", "--ignore", _RUFF_IGNORED, path)
    formatted = _ruff(app, "format", "--check", path)

    assert checked.returncode == 0, checked.stdout
    assert formatted.returncode == 0, formatted.stdout


def _ruff(app: TemporaryApp, *arguments: str) -> subprocess.CompletedProcess[str]:
    """Run the linter as an application would, with its defaults rather than this package's."""
    return subprocess.run(  # noqa: S603 — fixed arguments, the interpreter running the tests.
        [sys.executable, "-m", "ruff", *arguments, "--isolated"],
        cwd=app.project_dir,
        capture_output=True,
        text=True,
        check=False,
    )
