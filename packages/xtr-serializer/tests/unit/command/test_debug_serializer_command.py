"""``debug:serializer`` shows how a class is read and written, in debug mode only."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from xtr_console import Application, CommandTester, ExitCode
from xtr_console.bundle import ConsoleBundle
from xtr_dependency_injection import Kernel

from xtr_serializer.bundle import SerializerBundle
from xtr_serializer.command import DebugSerializerCommand

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

pytestmark = pytest.mark.anyio

_DESCRIBED = "tests.fixtures.described"


def _kernel(*, debug: bool) -> Kernel:
    return Kernel(
        __name__,
        env="test",
        debug=debug,
        bundles={SerializerBundle: {"all": True}, ConsoleBundle: {"all": True}},
        resources=(),
    )


@pytest.fixture
async def tester() -> AsyncIterator[CommandTester]:
    """Boot an application in debug mode and hand over the command."""
    async with await _kernel(debug=True).boot() as booted:
        application = await booted.container.get(Application)
        yield CommandTester(application, "debug:serializer", width=160)


def _lines(display: str) -> list[str]:
    """The rows of the tables, each cell stripped, the borders left out."""
    return [
        " ".join(cell.strip() for cell in line.strip("│ ").split("│"))
        for line in display.splitlines()
        if "│" in line
    ]


async def test_it_shows_each_field_of_a_dataclass_in_each_mode(tester: CommandTester) -> None:
    exit_code = await tester.execute([f"{_DESCRIBED}:Shipment"])

    assert exit_code == ExitCode.SUCCESS
    display = tester.display
    assert display.index("validation") < display.index("serialization")
    assert _lines(display).count("sent_at sent_at string (date-time) | null no null") == 2


async def test_it_shows_the_name_a_model_reads_and_writes_each_field_under(
    tester: CommandTester,
) -> None:
    exit_code = await tester.execute([f"{_DESCRIBED}.Account"])

    assert exit_code == ExitCode.SUCCESS
    lines = _lines(tester.display)
    assert "owner_name ownerName string yes" in lines
    assert lines.index("balance balanceIn integer no 0") < lines.index(
        "balance balanceOut integer no 0"
    )


async def test_it_shows_the_classes_of_a_hierarchy_by_name(tester: CommandTester) -> None:
    exit_code = await tester.execute(["tests.fixtures.hierarchies:Notice"])

    assert exit_code == ExitCode.SUCCESS
    lines = _lines(tester.display)
    assert "title title string yes" in lines
    assert "$type" in tester.display
    assert "reminder tests.fixtures.hierarchies.Reminder" in lines
    assert "outage tests.fixtures.hierarchies.Outage" in lines


async def test_a_class_of_a_hierarchy_with_no_name_shows_only_its_classes(
    tester: CommandTester,
) -> None:
    exit_code = await tester.execute(["tests.fixtures.hierarchies:Failure"])

    assert exit_code == ExitCode.SUCCESS
    lines = _lines(tester.display)
    assert "bounce tests.fixtures.hierarchies.Bounce" in lines
    assert not any(line.startswith("reason ") for line in lines)
    assert "never written itself" in tester.display


async def test_a_class_with_no_field_says_so(tester: CommandTester) -> None:
    exit_code = await tester.execute([f"{_DESCRIBED}:Empty"])

    assert exit_code == ExitCode.SUCCESS
    assert tester.display.count("No field.") == 2


async def test_a_field_with_no_json_schema_is_listed_with_any_type(tester: CommandTester) -> None:
    exit_code = await tester.execute([f"{_DESCRIBED}:Release"])

    assert exit_code == ExitCode.SUCCESS
    lines = _lines(tester.display)
    assert lines.index("version version any yes") < lines.index("version version string yes")


async def test_a_field_written_by_a_function_is_listed_in_both_modes(
    tester: CommandTester,
) -> None:
    exit_code = await tester.execute([f"{_DESCRIBED}:PriceLambda"])

    assert exit_code == ExitCode.SUCCESS
    assert _lines(tester.display).count("price price any yes") == 2
    assert "lambda" not in tester.display


@pytest.mark.parametrize(
    ("path", "said"),
    [
        (f"{_DESCRIBED}:Missing", "has no 'Missing'"),
        ("nowhere_at_all:Thing", "no module 'nowhere_at_all'"),
        (f"{_DESCRIBED}:not_a_class", "not a class"),
        (f"{_DESCRIBED}:Untyped", "pydantic has no schema"),
        ("builtins:int", "no object with fields"),
        ("builtins:type", "'builtins.type' cannot be shown: it is written as no object"),
        (f"{_DESCRIBED}:Crossed", "two of its fields are read under one name"),
        (f"{_DESCRIBED}:Misdescribed", "pydantic cannot describe it in a JSON schema"),
    ],
)
async def test_what_it_cannot_describe_is_refused(
    tester: CommandTester, path: str, said: str
) -> None:
    exit_code = await tester.execute([path])

    assert exit_code == ExitCode.FAILURE
    written = " ".join((tester.display + tester.error_display).split())
    assert said in written
    assert "pydantic.dev" not in written


async def test_outside_debug_mode_the_command_is_not_registered() -> None:
    async with await _kernel(debug=False).boot() as booted:
        assert not booted.container.has(DebugSerializerCommand)


async def test_an_installed_console_comes_along_with_the_command() -> None:
    kernel = Kernel(
        __name__, env="test", debug=True, bundles={SerializerBundle: {"all": True}}, resources=()
    )

    async with await kernel.boot() as booted:
        assert booted.container.has(DebugSerializerCommand)
