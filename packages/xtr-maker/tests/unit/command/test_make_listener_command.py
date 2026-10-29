"""Unit tests for :class:`xtr_maker.command.make_listener_command.MakeListenerCommand`."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from xtr_console import ExitCode
from xtr_event_dispatcher import EventDispatcher

from tests.conftest import FIXTURES
from tests.support.captured_style import CapturedStyle
from xtr_maker import FileManager, Generator, TemplateRenderer
from xtr_maker.command.make_listener_command import MakeListenerCommand
from xtr_maker.event import EventRegistry

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.anyio

_EXPECTED = FIXTURES / "expected" / "event"
_LISTENER = "src/app/event_listener/report_worker_started_listener.py"
_SUBSCRIBER = "src/app/event_subscriber/worker_stats_subscriber.py"


def _registry() -> EventRegistry:
    """The worker events of the messenger, and ``order.placed``, known by name only."""
    dispatcher = EventDispatcher()
    dispatcher.add_listener("order.placed", print)
    return EventRegistry(dispatcher, "app", ["xtr_messenger"])


async def _run(
    project: Path,
    style: CapturedStyle,
    *arguments: str,
    final_classes: bool = True,
) -> int:
    manager = FileManager(project, "app")
    generator = Generator(manager, TemplateRenderer(), final_classes=final_classes)
    command = MakeListenerCommand(manager, _registry())
    return await command(style.io, generator, *arguments)


def _read(project: Path, path: str) -> str:
    return (project / path).read_text(encoding="utf-8")


def _expected(name: str) -> str:
    return (_EXPECTED / name).read_text(encoding="utf-8")


def _batch() -> CapturedStyle:
    return CapturedStyle(interactive=False)


async def test_a_name_without_a_suffix_writes_a_listener_without_a_terminal(
    project: Path,
) -> None:
    code = await _run(project, _batch(), "report worker started", "WorkerStartedEvent")

    assert code == ExitCode.SUCCESS
    assert _read(project, _LISTENER) == _expected("report_worker_started_listener.py.txt")


async def test_a_name_ending_in_subscriber_writes_a_subscriber(project: Path) -> None:
    code = await _run(
        project, _batch(), "WorkerStatsSubscriber", "xtr_messenger.event:WorkerStartedEvent"
    )

    assert code == ExitCode.SUCCESS
    assert _read(project, _SUBSCRIBER) == _expected("worker_stats_subscriber.py.txt")


async def test_an_event_known_by_name_is_listened_to_by_that_name(project: Path) -> None:
    code = await _run(project, _batch(), "AuditOrderListener", "order.placed")

    assert code == ExitCode.SUCCESS
    assert _read(project, "src/app/event_listener/audit_order_listener.py") == _expected(
        "audit_order_listener.py.txt"
    )


async def test_a_dotted_path_names_the_event_class(project: Path) -> None:
    code = await _run(
        project, _batch(), "report worker started", "xtr_messenger.event.WorkerStartedEvent"
    )

    assert code == ExitCode.SUCCESS
    assert "from xtr_messenger.event import WorkerStartedEvent" in _read(project, _LISTENER)


async def test_the_shape_is_asked_when_the_name_does_not_pick_it(project: Path) -> None:
    style = CapturedStyle(["worker stats", "subscriber", "WorkerStartedEvent"])

    code = await _run(project, style)

    assert code == ExitCode.SUCCESS
    assert _read(project, _SUBSCRIBER) == _expected("worker_stats_subscriber.py.txt")


async def test_the_events_found_are_listed_before_the_event_is_asked(project: Path) -> None:
    style = CapturedStyle(["ReportWorkerStartedListener", "WorkerStartedEvent"])

    code = await _run(project, style)

    assert code == ExitCode.SUCCESS
    assert "* WorkerStartedEvent (xtr_messenger.event)" in style.lines
    assert '* "order.placed"' in style.lines


async def test_a_close_name_is_confirmed_as_the_event_it_was_close_to(project: Path) -> None:
    style = CapturedStyle(["y"])

    code = await _run(project, style, "ReportWorkerStartedListener", "WorkerStartdEvent")

    assert code == ExitCode.SUCCESS
    assert "Did you mean WorkerStartedEvent (xtr_messenger.event)?" in style.output
    assert "@as_event_listener(WorkerStartedEvent)" in _read(project, _LISTENER)


async def test_a_declined_suggestion_asks_for_the_event_again(project: Path) -> None:
    style = CapturedStyle(["n", "WorkerStoppedEvent"])

    code = await _run(project, style, "ReportWorkerStartedListener", "WorkerStartdEvent")

    assert code == ExitCode.SUCCESS
    assert "There is no event 'WorkerStartdEvent'." in style.output
    assert "@as_event_listener(WorkerStoppedEvent)" in _read(project, _LISTENER)


async def test_several_close_names_are_listed_and_the_event_asked_again(project: Path) -> None:
    style = CapturedStyle(["WorkerStoppedEvent"])

    code = await _run(project, style, "ReportWorkerStartedListener", "WorkerStaptedEvent")

    assert code == ExitCode.SUCCESS
    assert (
        "did you mean one of xtr_messenger.event:WorkerStartedEvent,"
        " xtr_messenger.event:WorkerStoppedEvent?"
    ) in style.output
    assert "@as_event_listener(WorkerStoppedEvent)" in _read(project, _LISTENER)


async def test_without_a_terminal_a_close_name_is_refused_naming_what_it_was_close_to(
    project: Path,
) -> None:
    style = _batch()

    code = await _run(project, style, "ReportWorkerStartedListener", "WorkerStartdEvent")

    assert code == ExitCode.INVALID
    assert (
        "There is no event 'WorkerStartdEvent';"
        " did you mean xtr_messenger.event:WorkerStartedEvent?"
    ) in style.output
    assert not (project / "src/app/event_listener").exists()


async def test_without_a_terminal_an_unknown_event_is_refused(project: Path) -> None:
    style = _batch()

    code = await _run(project, style, "ReportWorkerStartedListener", "Nothing")

    assert code == ExitCode.INVALID
    assert "There is no event 'Nothing'" in style.output


async def test_an_unknown_event_is_kept_as_a_name_once_confirmed(project: Path) -> None:
    style = CapturedStyle(["y"])

    code = await _run(project, style, "AuditListener", "billing.invoice_sent")

    assert code == ExitCode.SUCCESS
    source = _read(project, "src/app/event_listener/audit_listener.py")
    assert '@as_event_listener("billing.invoice_sent")' in source
    assert "async def on_billing_invoice_sent(self, event: Event) -> None:" in source


async def test_an_event_name_the_code_cannot_spell_is_refused(project: Path) -> None:
    style = CapturedStyle(["y"])

    code = await _run(project, style, "AuditListener", 'say "hi"')

    assert code == ExitCode.INVALID
    assert "cannot be written" in style.output


@pytest.mark.parametrize(
    ("arguments", "expected"),
    [((), "make:listener <name> <event>"), (("AuditListener",), "Name the event to listen to")],
)
async def test_without_a_terminal_what_is_missing_is_refused(
    project: Path, arguments: tuple[str, ...], expected: str
) -> None:
    style = _batch()

    code = await _run(project, style, *arguments)

    assert code == ExitCode.INVALID
    assert expected in style.output


async def test_an_invalid_name_is_asked_again(project: Path) -> None:
    style = CapturedStyle(["class", "ReportWorkerStartedListener", "WorkerStartedEvent"])

    code = await _run(project, style)

    assert code == ExitCode.SUCCESS
    assert "'Class' cannot name a class" in style.output
    assert (project / _LISTENER).is_file()


async def test_the_event_is_asked_three_times_at_most(project: Path) -> None:
    code = await _run(project, CapturedStyle(["AuditListener", "", "", ""]))

    assert code == ExitCode.INVALID
    assert not (project / "src/app/event_listener").exists()


async def test_a_subpackage_moves_the_class_under_its_folder(project: Path) -> None:
    code = await _run(project, _batch(), "worker.StatsSubscriber", "WorkerStartedEvent")

    assert code == ExitCode.SUCCESS
    assert (project / "src/app/event_subscriber/worker/stats_subscriber.py").is_file()


async def test_classes_are_left_open_when_final_classes_is_off(project: Path) -> None:
    code = await _run(
        project, _batch(), "WorkerStatsSubscriber", "WorkerStartedEvent", final_classes=False
    )

    assert code == ExitCode.SUCCESS
    assert "final" not in _read(project, _SUBSCRIBER)


async def test_the_next_step_names_the_file_and_the_method(project: Path) -> None:
    style = _batch()

    _ = await _run(project, style, "report worker started", "WorkerStartedEvent")

    assert style.lines[-2:] == [
        "Next:",
        f"- Open {_LISTENER} and write what on_worker_started_event does.",
    ]


async def test_an_existing_class_is_refused(project: Path) -> None:
    (project / "src/app/event_listener").mkdir()
    _ = (project / _LISTENER).write_text('"""Mine."""\n', encoding="utf-8")
    style = _batch()

    code = await _run(project, style, "report worker started", "WorkerStartedEvent")

    assert code == ExitCode.FAILURE
    assert "report_worker_started_listener.py already exists" in style.output
    assert _read(project, _LISTENER) == '"""Mine."""\n'
