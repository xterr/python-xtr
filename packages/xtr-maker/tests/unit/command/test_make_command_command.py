"""Unit tests for :class:`xtr_maker.command.make_command_command.MakeCommandCommand`."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from xtr_console import CommandsLocator, ExitCode, as_command

from tests.conftest import FIXTURES
from tests.support.captured_style import CapturedStyle
from xtr_maker import FileManager, Generator, TemplateRenderer
from xtr_maker.command.make_command_command import MakeCommandCommand

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

pytestmark = pytest.mark.anyio

_EXPECTED = FIXTURES / "expected" / "command"
_REPORT = "src/app/command/send_report_command.py"


async def _run(  # noqa: PLR0913 — the command's own parameters, plus what it runs against.
    project: Path,
    style: CapturedStyle,
    name: str | None = None,
    *,
    argument: list[str] | None = None,
    option: list[str] | None = None,
    final_classes: bool = True,
    commands: CommandsLocator | None = None,
) -> int:
    manager = FileManager(project, "app")
    generator = Generator(manager, TemplateRenderer(), final_classes=final_classes)
    command = MakeCommandCommand(manager, commands or CommandsLocator())
    return await command(style.io, generator, name, argument=argument, option=option)


def _read(project: Path, path: str = _REPORT) -> str:
    return (project / path).read_text(encoding="utf-8")


def _batch() -> CapturedStyle:
    return CapturedStyle(interactive=False)


async def test_flags_write_the_arguments_and_options(project: Path) -> None:
    code = await _run(
        project,
        _batch(),
        "app:send-report",
        argument=["recipient", "method:http.HTTPMethod", "cc?:list"],
        option=["dry-run", "limit:int", "status:http.HTTPStatus"],
    )

    assert code == ExitCode.SUCCESS
    assert _read(project) == (_EXPECTED / "send_report_command.py.txt").read_text(encoding="utf-8")


async def test_without_parameters_a_demonstration_pair_is_written(project: Path) -> None:
    code = await _run(project, _batch(), "app:greet")

    assert code == ExitCode.SUCCESS
    assert _read(project, "src/app/command/greet_command.py") == (
        _EXPECTED / "greet_command.py.txt"
    ).read_text(encoding="utf-8")


async def test_options_alone_are_written_without_the_demonstration_argument(
    project: Path,
) -> None:
    code = await _run(project, _batch(), "app:send-report", option=["dry-run"])

    assert code == ExitCode.SUCCESS
    assert "(self, io: ConsoleStyle, *, dry_run: bool = False) -> int:" in _read(project)


async def test_answers_declare_the_command_and_its_parameters(project: Path) -> None:
    style = CapturedStyle(
        [
            "app:send-report",
            "Send the monthly report.",
            "recipient",
            "str",
            "Who receives it.",
            "y",
            "cc",
            "list",
            "",
            "n",
            "dry-run",
            "bool",
            "Print it instead.",
            "limit",
            "int",
            "",
            "",
        ]
    )

    code = await _run(project, style)

    assert code == ExitCode.SUCCESS, style.output
    source = _read(project)
    assert '@as_command("app:send-report", description="Send the monthly report.")' in source
    assert "        recipient: str,\n        cc: list[str] | None = None,\n        *,\n" in source
    assert "        dry_run: bool = False,\n        limit: int | None = None,\n" in source
    assert "            recipient: Who receives it.\n" in source
    assert "            cc: Cc.\n" in source
    assert "            dry_run: Print it instead.\n" in source


async def test_after_an_optional_argument_the_next_is_not_asked_whether_required(
    project: Path,
) -> None:
    style = CapturedStyle(
        ["app:send-report", "", "first", "str", "", "n", "second", "str", "", "", ""]
    )

    code = await _run(project, style)

    assert code == ExitCode.SUCCESS, style.output
    assert style.output.count("Is it required?") == 1
    assert "first: str | None = None,\n        second: str | None = None,\n" in _read(project)


async def test_an_invalid_or_taken_parameter_name_is_asked_again(project: Path) -> None:
    style = CapturedStyle(
        ["app:send-report", "", "Bad", "io", "name", "str", "", "y", "", "name", "yell", "bool"]
    )

    code = await _run(project, style)

    assert code == ExitCode.SUCCESS, style.output
    assert "'Bad' cannot name an argument" in style.output
    assert "'io' cannot name an argument" in style.output
    assert "There is already a parameter named 'name'." in style.output
    assert "name: str, *, yell: bool = False" in _read(project)


async def test_an_enum_type_asks_for_its_class_until_it_imports(project: Path) -> None:
    style = CapturedStyle(
        ["app:send-report", "", "status", "enum", "nope", "http.HTTPStatus", "", "y", "", ""]
    )

    code = await _run(project, style)

    assert code == ExitCode.SUCCESS, style.output
    assert "There is no type 'nope'" in style.output
    assert "status: HTTPStatus" in _read(project)


async def test_an_enum_class_answered_wrong_three_times_ends_the_run(project: Path) -> None:
    style = CapturedStyle(["app:send-report", "", "status", "enum", "a", "b", "c"])

    code = await _run(project, style)

    assert code == ExitCode.INVALID
    assert not (project / _REPORT).exists()


async def test_answering_no_parameter_writes_a_command_taking_none(project: Path) -> None:
    style = CapturedStyle(["app:send-report", "", "", ""])

    code = await _run(project, style)

    assert code == ExitCode.SUCCESS, style.output
    source = _read(project)
    assert "async def __call__(self, io: ConsoleStyle) -> int:" in source
    assert "escape" not in source


async def test_no_argument_is_asked_after_a_list_argument(project: Path) -> None:
    style = CapturedStyle(["app:send-report", "", "files", "list", "", "y", ""])

    code = await _run(project, style)

    assert code == ExitCode.SUCCESS, style.output
    assert style.output.count("A new argument's name") == 1
    assert "files: list[str]) -> int:" in _read(project)


async def test_classes_are_left_open_when_final_classes_is_off(project: Path) -> None:
    code = await _run(project, _batch(), "app:send-report", final_classes=False)

    assert code == ExitCode.SUCCESS
    assert "final" not in _read(project)


async def test_the_next_steps_name_the_help_and_the_file(project: Path) -> None:
    style = _batch()

    _ = await _run(project, style, "app:send-report")

    assert style.lines[-3:] == [
        "Next:",
        "- Run app:send-report --help to see its arguments and options.",
        f"- Open {_REPORT} and write what it does.",
    ]


async def test_without_a_terminal_a_missing_name_is_refused(project: Path) -> None:
    style = _batch()

    code = await _run(project, style)

    assert code == ExitCode.INVALID
    assert "make:command <name>" in style.output


@pytest.mark.parametrize("name", ["app:send report", "app::report", ":report", "app:-x", "a!"])
async def test_a_name_the_console_cannot_take_is_refused(project: Path, name: str) -> None:
    style = _batch()

    code = await _run(project, style, name)

    assert code == ExitCode.INVALID
    assert "cannot name a command" in style.output


async def test_a_name_whose_last_part_cannot_name_a_class_is_refused(project: Path) -> None:
    style = _batch()

    code = await _run(project, style, "app:123")

    assert code == ExitCode.INVALID
    assert "'123Command' cannot name a class" in style.output


async def test_a_name_a_command_already_answers_to_is_refused(project: Path) -> None:
    commands = CommandsLocator()

    @as_command("app:report", aliases="app:send-report", registry=commands)
    def report() -> int:
        return ExitCode.SUCCESS

    style = _batch()

    code = await _run(project, style, "app:send-report", commands=commands)

    assert code == ExitCode.INVALID
    assert "The command 'app:report' already answers to 'app:send-report'." in style.output
    assert not (project / _REPORT).exists()


@pytest.mark.parametrize("answers", [("a b", "app:", "app:1"), ()])
async def test_the_name_is_asked_three_times_at_most(project: Path, answers: Sequence[str]) -> None:
    code = await _run(project, CapturedStyle(answers))

    assert code == ExitCode.INVALID
    assert not (project / "src/app/command").exists()


async def test_an_invalid_answer_is_asked_again(project: Path) -> None:
    style = CapturedStyle(["a b", "app:send-report"])

    code = await _run(project, style, option=["dry-run"])

    assert code == ExitCode.SUCCESS
    assert "'a b' cannot name a command" in style.output


async def test_a_blank_description_keeps_the_placeholder(project: Path) -> None:
    style = CapturedStyle(["app:send-report", " "])

    code = await _run(project, style, option=["dry-run"])

    assert code == ExitCode.SUCCESS
    assert 'description="Describe what app:send-report does."' in _read(project)


@pytest.mark.parametrize(
    ("arguments", "options", "message"),
    [
        (["force:bool"], [], "cannot be a bool"),
        (["first?", "second"], [], "Required argument 'second' cannot follow"),
        (["files:list", "name"], [], "List argument 'files' takes every value left"),
        (["name"], ["name"], "Two parameters are named 'name'"),
        ([], ["limit?:int"], "never required"),
        ([], ["quiet"], "every command already takes --quiet"),
        (["value:Missing"], [], "There is no type 'Missing'"),
    ],
)
async def test_parameters_the_signature_cannot_hold_are_refused(
    project: Path, arguments: list[str], options: list[str], message: str
) -> None:
    style = _batch()

    code = await _run(project, style, "app:send-report", argument=arguments, option=options)

    assert code == ExitCode.INVALID
    assert message in style.output
    assert not (project / "src/app/command").exists()


async def test_an_existing_command_file_is_refused_and_kept(project: Path) -> None:
    (project / "src/app/command").mkdir()
    _ = (project / _REPORT).write_text('"""Mine."""\n', encoding="utf-8")
    style = _batch()

    code = await _run(project, style, "app:send-report")

    assert code == ExitCode.FAILURE
    assert "send_report_command.py already exists" in style.output
    assert _read(project) == '"""Mine."""\n'
