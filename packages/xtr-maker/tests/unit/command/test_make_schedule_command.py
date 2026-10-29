"""Unit tests for :class:`xtr_maker.command.make_schedule_command.MakeScheduleCommand`."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from xtr_console import ExitCode
from xtr_dependency_injection.diagnostics import KernelReport
from xtr_messenger import as_message
from xtr_scheduler import Schedule, ScheduleProviderInterface
from xtr_scheduler.schedule_provider_locator import ScheduleProviderLocator

from tests.conftest import FIXTURES
from tests.support.captured_style import CapturedStyle
from xtr_maker import FileManager, Generator, TemplateRenderer
from xtr_maker.command.make_schedule_command import MakeScheduleCommand

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

pytestmark = pytest.mark.anyio

_EXPECTED = FIXTURES / "expected" / "scheduler"
_PROVIDER = "src/app/scheduler/report_schedule.py"
_PEERS = ("cache", "lock")


def _declared_in(module: str) -> Callable[[type], type]:
    """Move the class into ``module``, as if the application declared it there."""

    def move(declared: type) -> type:
        declared.__module__ = module
        return declared

    return move


@as_message(name="tests.maker.schedule.restock_check.v1")
@_declared_in("app.message.restock_check")
@dataclass(frozen=True, slots=True)
class RestockCheck:
    pass


@as_message(name="tests.maker.schedule.reindex_catalog.v1")
@_declared_in("app.message.reindex_catalog")
@dataclass(frozen=True, slots=True)
class ReindexCatalog:
    reason: str


@as_message(name="tests.maker.schedule.foreign.v1")
@_declared_in("elsewhere.message.foreign")
@dataclass(frozen=True, slots=True)
class Foreign:
    """Declared by another package: never offered."""


class ShopSchedule(ScheduleProviderInterface):
    def get_schedule(self) -> Schedule:
        return Schedule()


@dataclass(frozen=True)
class _Kernel:
    bundles: tuple[str, ...]
    name: str = "app"
    environment: str = "test"
    debug: bool = False
    project_dir: Path = field(default_factory=Path)
    report: KernelReport = field(default_factory=KernelReport)


_SCHEDULES = ScheduleProviderLocator({"shop": ShopSchedule(), "nightly": Schedule()})


async def _run(  # noqa: PLR0913 — the command's own parameters, plus what it runs against.
    project: Path,
    style: CapturedStyle,
    name: str | None = None,
    *,
    bundles: Sequence[str] = _PEERS,
    schedule: str | None = None,
    message: str | None = None,
    stateful: bool = False,
    lock: bool = False,
) -> int:
    manager = FileManager(project, "app")
    generator = Generator(manager, TemplateRenderer())
    command = MakeScheduleCommand(manager, _SCHEDULES, _Kernel(tuple(bundles)))
    return await command(
        style.io,
        generator,
        name,
        schedule=schedule,
        message=message,
        stateful=stateful,
        lock=lock,
    )


def _read(project: Path) -> str:
    return (project / _PROVIDER).read_text(encoding="utf-8")


def _expected(name: str) -> str:
    return (_EXPECTED / name).read_text(encoding="utf-8")


def _batch() -> CapturedStyle:
    return CapturedStyle(interactive=False)


async def test_flags_write_a_stateful_locked_schedule_sending_the_message(project: Path) -> None:
    code = await _run(
        project,
        _batch(),
        "report",
        schedule="reports",
        message="RestockCheck",
        stateful=True,
        lock=True,
    )

    assert code == ExitCode.SUCCESS
    assert _read(project) == _expected("message_stateful_lock.py.txt")


async def test_without_a_terminal_the_default_schedule_is_empty(project: Path) -> None:
    code = await _run(project, _batch(), "report")

    assert code == ExitCode.SUCCESS
    assert _read(project) == _expected("empty.py.txt")


async def test_a_message_taking_arguments_is_described_not_built(project: Path) -> None:
    style = _batch()

    code = await _run(project, style, "report", message="ReindexCatalog")

    assert code == ExitCode.SUCCESS
    source = _read(project)
    assert '# RecurringMessage.every("1 hour", ReindexCatalog(...)).' in source
    assert "import ReindexCatalog" not in source
    assert "add ReindexCatalog once its arguments are known" in style.output


async def test_a_message_is_accepted_by_its_module_and_class(project: Path) -> None:
    code = await _run(project, _batch(), "report", message="app.message.restock_check:RestockCheck")

    assert code == ExitCode.SUCCESS
    assert "from app.message.restock_check import RestockCheck" in _read(project)


async def test_answers_pick_the_schedule_the_message_and_both_options(project: Path) -> None:
    style = CapturedStyle(["report", "reports", "RestockCheck", "y", "y"])

    code = await _run(project, style)

    assert code == ExitCode.SUCCESS
    assert _read(project) == _expected("message_stateful_lock.py.txt")


async def test_the_options_are_not_asked_without_their_bundles(project: Path) -> None:
    style = CapturedStyle(["report", "", ""])

    code = await _run(project, style, bundles=())

    assert code == ExitCode.SUCCESS
    assert "cache pool?" not in style.output
    assert "lock only?" not in style.output
    assert _read(project) == _expected("empty.py.txt")


async def test_only_the_applications_messages_are_offered(project: Path) -> None:
    style = CapturedStyle(["report", "", ""])

    _ = await _run(project, style, bundles=())

    assert "[empty schedule]/ReindexCatalog/RestockCheck" in style.output
    assert "Foreign" not in style.output


async def test_the_next_steps_name_the_file_and_the_worker(project: Path) -> None:
    style = _batch()

    _ = await _run(project, style, "report", schedule="reports")

    assert style.lines[-3:] == [
        "Next:",
        f"- Open {_PROVIDER} and set what it sends, and how often.",
        "- Run it: messenger:consume scheduler_reports",
    ]


async def test_a_schedule_only_tasks_declare_may_get_a_provider(project: Path) -> None:
    code = await _run(project, _batch(), "report", schedule="nightly")

    assert code == ExitCode.SUCCESS
    assert '@as_schedule("nightly")' in _read(project)


async def test_a_schedule_a_provider_already_provides_is_refused(project: Path) -> None:
    style = _batch()

    code = await _run(project, style, "report", schedule="shop")

    assert code == ExitCode.INVALID
    assert "The schedule 'shop' is already provided by" in style.output
    assert "ShopSchedule; pick another name." in style.output
    assert not (project / "src/app/scheduler").exists()


async def test_a_taken_schedule_is_asked_again(project: Path) -> None:
    style = CapturedStyle(["report", "shop", "reports", "", "", ""])

    code = await _run(project, style)

    assert code == ExitCode.SUCCESS
    assert "already provided by" in style.output
    assert '@as_schedule("reports")' in _read(project)


async def test_an_invalid_schedule_name_is_refused(project: Path) -> None:
    style = _batch()

    code = await _run(project, style, "report", schedule="two words")

    assert code == ExitCode.INVALID
    assert "'two words' cannot name a schedule" in style.output


@pytest.mark.parametrize(
    ("stateful", "lock", "refused"),
    [
        (True, False, "--stateful needs the cache bundle"),
        (False, True, "--lock needs the lock bundle"),
    ],
)
async def test_an_option_is_refused_without_its_bundle(
    project: Path, stateful: bool, lock: bool, refused: str
) -> None:
    style = _batch()

    code = await _run(project, style, "report", bundles=(), stateful=stateful, lock=lock)

    assert code == ExitCode.INVALID
    assert refused in style.output
    assert not (project / "src/app/scheduler").exists()


async def test_an_unknown_message_is_refused_naming_the_declared_ones(project: Path) -> None:
    style = _batch()

    code = await _run(project, style, "report", message="Foreign")

    assert code == ExitCode.INVALID
    assert "There is no message 'Foreign' in app; the declared ones are" in style.output
    assert "ReindexCatalog, RestockCheck." in style.output


async def test_a_message_is_refused_when_the_application_declares_none(tmp_path: Path) -> None:
    _ = (tmp_path / "pyproject.toml").write_text('[project]\nname = "bare"\n', encoding="utf-8")
    (tmp_path / "bare").mkdir()
    manager = FileManager(tmp_path, "bare")
    command = MakeScheduleCommand(manager, _SCHEDULES, _Kernel(()))
    style = _batch()

    code = await command(style.io, Generator(manager, TemplateRenderer()), "x", message="Ping")

    assert code == ExitCode.INVALID
    assert "No message is declared in bare" in style.output


async def test_without_a_terminal_a_missing_name_is_refused(project: Path) -> None:
    style = _batch()

    code = await _run(project, style)

    assert code == ExitCode.INVALID
    assert "make:schedule <name>" in style.output


async def test_an_invalid_name_is_asked_again(project: Path) -> None:
    style = CapturedStyle(["a!", "report", "", "", "", ""])

    code = await _run(project, style)

    assert code == ExitCode.SUCCESS
    assert "'a!' cannot name a class" in style.output
    assert (project / _PROVIDER).is_file()


async def test_an_existing_provider_is_refused(project: Path) -> None:
    (project / "src/app/scheduler").mkdir()
    _ = (project / _PROVIDER).write_text('"""Mine."""\n', encoding="utf-8")
    style = _batch()

    code = await _run(project, style, "report")

    assert code == ExitCode.FAILURE
    assert "report_schedule.py already exists" in style.output
    assert _read(project) == '"""Mine."""\n'
