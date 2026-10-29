"""Unit tests for :class:`xtr_maker.command.make_message_command.MakeMessageCommand`."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from xtr_console import ExitCode
from xtr_messenger import MessageBusConfig, TransportConfig

from tests.conftest import FIXTURES
from tests.support.captured_style import CapturedStyle
from xtr_maker import FileManager, Generator, TemplateRenderer
from xtr_maker.command.make_message_command import MakeMessageCommand

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

pytestmark = pytest.mark.anyio

_EXPECTED = FIXTURES / "expected" / "message"
_TRANSPORTS = MessageBusConfig(
    transports={"async": TransportConfig("in-memory://"), "sync": TransportConfig("sync://")}
)
_MESSAGE = "src/app/message/place_order.py"
_HANDLER = "src/app/message_handler/place_order_handler.py"


async def _run(  # noqa: PLR0913 — the command's own parameters, plus what it runs against.
    project: Path,
    style: CapturedStyle,
    name: str | None = None,
    *,
    config: MessageBusConfig = _TRANSPORTS,
    transport: str | None = None,
    wire_name: str | None = None,
    final_classes: bool = True,
) -> int:
    manager = FileManager(project, "app")
    generator = Generator(manager, TemplateRenderer(), final_classes=final_classes)
    command = MakeMessageCommand(manager, config)
    return await command(style.io, generator, name, transport=transport, wire_name=wire_name)


def _read(project: Path, path: str) -> str:
    return (project / path).read_text(encoding="utf-8")


def _expected(case: str, name: str) -> str:
    return (_EXPECTED / case / name).read_text(encoding="utf-8")


def _interactive(*inputs: str) -> CapturedStyle:
    return CapturedStyle(inputs)


def _batch() -> CapturedStyle:
    return CapturedStyle(interactive=False)


async def test_flags_write_the_message_with_its_transport_and_wire_name(project: Path) -> None:
    code = await _run(
        project, _batch(), "place order", transport="async", wire_name="app.order.place.v2"
    )

    assert code == ExitCode.SUCCESS
    assert _read(project, _MESSAGE) == _expected("transport", "place_order.py.txt")
    assert _read(project, _HANDLER) == _expected("transport", "place_order_handler.py.txt")


async def test_answers_write_a_message_without_transport_when_none_is_configured(
    project: Path,
) -> None:
    style = _interactive("place order", "")

    code = await _run(project, style, config=MessageBusConfig())

    assert code == ExitCode.SUCCESS
    assert "transport" not in style.output
    assert _read(project, _MESSAGE) == _expected("no_transport", "place_order.py.txt")
    assert _read(project, _HANDLER) == _expected("no_transport", "place_order_handler.py.txt")


async def test_the_transport_is_picked_among_the_configured_ones(project: Path) -> None:
    code = await _run(project, _interactive("place order", "sync", ""))

    assert code == ExitCode.SUCCESS
    assert '@as_message(name="app.place_order.v1", transport="sync")' in _read(project, _MESSAGE)


async def test_picking_no_transport_leaves_it_to_the_routing_table(project: Path) -> None:
    code = await _run(project, _interactive("place order", "[no transport]", ""))

    assert code == ExitCode.SUCCESS
    assert '@as_message(name="app.place_order.v1")' in _read(project, _MESSAGE)


async def test_without_a_terminal_the_defaults_apply_beside_the_name(project: Path) -> None:
    code = await _run(project, _batch(), "PlaceOrder")

    assert code == ExitCode.SUCCESS
    assert '@as_message(name="app.place_order.v1")' in _read(project, _MESSAGE)


async def test_a_subpackage_moves_both_classes_and_names_the_wire_after_it(
    project: Path,
) -> None:
    code = await _run(project, _batch(), "ordering.place order")

    assert code == ExitCode.SUCCESS
    assert '@as_message(name="app.ordering.place_order.v1")' in _read(
        project, "src/app/message/ordering/place_order.py"
    )
    assert "from app.message.ordering.place_order import PlaceOrder" in _read(
        project, "src/app/message_handler/ordering/place_order_handler.py"
    )


async def test_a_decorator_too_long_for_a_line_takes_one_argument_per_line(
    project: Path,
) -> None:
    wire = "app.a_very_long_bounded_context.ordering.place_order.v1"

    code = await _run(project, _batch(), "place order", transport="async", wire_name=wire)

    assert code == ExitCode.SUCCESS
    assert f'@as_message(\n    name="{wire}",\n    transport="async",\n)\n' in _read(
        project, _MESSAGE
    )


async def test_classes_are_left_open_when_final_classes_is_off(project: Path) -> None:
    code = await _run(project, _batch(), "place order", final_classes=False)

    assert code == ExitCode.SUCCESS
    for path in (_MESSAGE, _HANDLER):
        source = _read(project, path)
        assert "final" not in source


async def test_the_next_steps_name_both_files(project: Path) -> None:
    style = _batch()

    _ = await _run(project, style, "place order")

    assert style.lines[-3:] == [
        "Next:",
        f"- Open {_MESSAGE} and add its fields.",
        f"- Open {_HANDLER} and write what handling it does.",
    ]


async def test_without_a_terminal_a_missing_name_is_refused(project: Path) -> None:
    style = _batch()

    code = await _run(project, style)

    assert code == ExitCode.INVALID
    assert "make:message <name>" in style.output
    assert not (project / "src/app/message").exists()


async def test_an_unknown_transport_is_refused_naming_the_configured_ones(
    project: Path,
) -> None:
    style = _batch()

    code = await _run(project, style, "place order", transport="queue")

    assert code == ExitCode.INVALID
    assert "There is no transport 'queue'; the configured ones are async, sync." in style.output
    assert not (project / "src/app/message").exists()


async def test_a_transport_is_refused_when_none_is_configured(project: Path) -> None:
    style = _batch()

    code = await _run(project, style, "place order", config=MessageBusConfig(), transport="async")

    assert code == ExitCode.INVALID
    assert "No transports are configured" in style.output


async def test_an_empty_wire_name_is_refused(project: Path) -> None:
    style = _batch()

    code = await _run(project, style, "place order", wire_name=" ")

    assert code == ExitCode.INVALID
    assert "The wire name cannot be empty." in style.output


async def test_an_invalid_name_on_the_command_line_is_refused(project: Path) -> None:
    style = _batch()

    code = await _run(project, style, "class")

    assert code == ExitCode.INVALID
    assert "'Class' cannot name a class" in style.output


async def test_an_invalid_answer_is_asked_again(project: Path) -> None:
    style = _interactive("class", "place order", "")

    code = await _run(project, style, config=MessageBusConfig())

    assert code == ExitCode.SUCCESS
    assert "'Class' cannot name a class" in style.output
    assert (project / _MESSAGE).is_file()


@pytest.mark.parametrize("answers", [("class", "a!", "1x"), ()])
async def test_the_name_is_asked_three_times_at_most(project: Path, answers: Sequence[str]) -> None:
    code = await _run(project, _interactive(*answers), config=MessageBusConfig())

    assert code == ExitCode.INVALID
    assert not (project / "src/app/message").exists()


async def test_an_existing_message_is_refused_and_nothing_is_written(project: Path) -> None:
    (project / "src/app/message").mkdir()
    _ = (project / _MESSAGE).write_text('"""Mine."""\n', encoding="utf-8")
    style = _batch()

    code = await _run(project, style, "place order")

    assert code == ExitCode.FAILURE
    assert "src/app/message/place_order.py already exists" in style.output
    assert _read(project, _MESSAGE) == '"""Mine."""\n'
    assert not (project / "src/app/message_handler").exists()


async def test_an_existing_handler_is_refused_and_the_message_is_not_written(
    project: Path,
) -> None:
    (project / "src/app/message_handler").mkdir()
    _ = (project / _HANDLER).write_text('"""Mine."""\n', encoding="utf-8")
    style = _batch()

    code = await _run(project, style, "place order")

    assert code == ExitCode.FAILURE
    assert "place_order_handler.py already exists" in style.output
    assert not (project / _MESSAGE).exists()
