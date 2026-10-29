"""Unit tests for :class:`xtr_maker.command_source.CommandSource`."""

from __future__ import annotations

from typing import cast

import pytest

from xtr_maker.command_parameter import CommandParameter
from xtr_maker.command_source import CommandSource
from xtr_maker.exception import InvalidArgumentError

_NAME = CommandParameter("name", "str", description="Name.")
_CC = CommandParameter("cc", "list[str]", required=False, description="Cc.")


def _option(
    name: str, value_type: str = "bool", description: str = "An option."
) -> CommandParameter:
    return CommandParameter(name, value_type, option=True, required=False, description=description)


def _context(
    arguments: list[CommandParameter],
    options: list[CommandParameter] | None = None,
    *,
    description: str = "Do it.",
    root_package: str = "app",
) -> dict[str, object]:
    source = CommandSource("app:do", description, arguments, options or [])
    return source.context(root_package, final_classes=True)


def test_two_parameters_cannot_share_a_name() -> None:
    with pytest.raises(InvalidArgumentError, match="Two parameters are named 'name'"):
        _ = CommandSource("app:do", "Do it.", [_NAME], [_option("name")])


def test_a_list_argument_must_come_last() -> None:
    with pytest.raises(InvalidArgumentError, match="List argument 'cc' takes every value left"):
        _ = CommandSource("app:do", "Do it.", [_CC, _NAME], [])


def test_a_required_argument_cannot_follow_an_optional_one() -> None:
    optional = CommandParameter("first", "str", required=False)

    with pytest.raises(
        InvalidArgumentError,
        match="Required argument 'name' cannot follow optional argument 'first'",
    ):
        _ = CommandSource("app:do", "Do it.", [optional, _NAME], [])


def test_a_short_signature_stays_on_one_line() -> None:
    context = _context([_NAME], [_option("yell")])

    assert context["signature"] == (
        "    async def __call__(self, io: ConsoleStyle, name: str, *, yell: bool = False) -> int:"
    )


def test_without_options_there_is_no_bare_star() -> None:
    assert "*" not in str(_context([_NAME, _CC])["signature"])


def test_a_long_signature_takes_one_parameter_per_line() -> None:
    context = _context([_NAME, _CC], [_option("dry_run")])

    assert context["signature"] == (
        "    async def __call__(\n"
        "        self,\n"
        "        io: ConsoleStyle,\n"
        "        name: str,\n"
        "        cc: list[str] | None = None,\n"
        "        *,\n"
        "        dry_run: bool = False,\n"
        "    ) -> int:"
    )


def test_more_than_five_parameters_carry_the_reason_the_linter_asks_for() -> None:
    options = [_option(name) for name in ("one", "two", "three", "four", "five")]

    signature = str(_context([], options)["signature"])

    assert signature.startswith(
        "    async def __call__(  # noqa: PLR0913 — one parameter per argument and option.\n"
    )


def test_five_parameters_need_no_reason() -> None:
    options = [_option(name) for name in ("one", "two", "three", "four")]

    assert "noqa" not in str(_context([], options)["signature"])


def test_a_long_description_takes_one_decorator_argument_per_line() -> None:
    description = "Send the monthly report to every recipient on the list, then archive it."

    context = _context([], description=description)

    assert (
        context["as_command"] == f'@as_command(\n    "app:do",\n    description="{description}",\n)'
    )


def test_long_help_text_wraps_under_its_name() -> None:
    words = "word " * 20
    parameter = CommandParameter("name", "str", description=words.strip())

    lines = cast("list[str]", _context([parameter])["arguments"])

    assert lines[0] == "            io: Where the command writes."
    assert all(len(line) <= 88 for line in lines)
    assert lines[1].startswith("            name: word")
    assert lines[2].startswith("                word")


def test_every_parameter_is_echoed() -> None:
    context = _context([_NAME], [_option("yell")])

    assert context["body"] == ['io.text(escape(f"{name=}"))', 'io.text(escape(f"{yell=}"))']


def test_a_command_without_parameters_imports_no_escape() -> None:
    context = _context([])

    assert "escape" not in str(context["imports"])
    assert context["body"] == []


def test_an_enum_class_is_imported_at_runtime_without_a_linter_directive() -> None:
    status = CommandParameter("status", "http.HTTPStatus")

    imports = str(_context([status])["imports"])

    assert "from http import HTTPStatus\n" in imports
    assert "noqa" not in imports


def test_an_enum_from_a_module_already_imported_joins_its_statement() -> None:
    level = _option("level", "xtr_console.Verbosity")

    context = _context([], [level])

    assert "noqa" not in str(context["imports"])
    assert "Verbosity" in str(context["imports"])
    assert "level: Verbosity | None = None" in str(context["signature"])
