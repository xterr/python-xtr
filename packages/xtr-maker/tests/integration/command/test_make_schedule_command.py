"""``make:schedule`` in an application: run through its console, then discovered by its kernel."""

from __future__ import annotations

import subprocess
import sys
from typing import TYPE_CHECKING, cast

import pytest
from xtr_cache.bundle import CacheBundle
from xtr_console import ExitCode
from xtr_lock.bundle import LockBundle
from xtr_scheduler import ScheduleProviderInterface
from xtr_scheduler.bundle import SchedulerBundle
from xtr_scheduler.schedule_provider_locator import ScheduleProviderLocator

from tests.support.temporary_app import TemporaryApp

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

pytestmark = pytest.mark.anyio

_MESSAGE = '''"""A message the schedule can send."""

from __future__ import annotations

from dataclasses import dataclass

from xtr_messenger import as_message


@as_message
@dataclass(frozen=True, slots=True)
class RestockCheck:
    """Check the stock."""
'''

_SHOP_SCHEDULE = '''"""A schedule the application already provides."""

from __future__ import annotations

from xtr_scheduler import Schedule, ScheduleProviderInterface
from xtr_scheduler.decorator import as_schedule


@as_schedule("shop")
class ShopSchedule(ScheduleProviderInterface):
    def get_schedule(self) -> Schedule:
        return Schedule()
'''

_GENERATED = "scheduler/report_schedule.py"

_RUFF_IGNORED = "CPY001,D203,D213,COM812,ISC001,TC001,TC002,TC003"
"""What an application selecting every rule turns off: no copyright header, the formatter's
conflicts, one of each pair of docstring conventions that exclude each other, and moving
imports under ``TYPE_CHECKING`` — the container reads constructor annotations at runtime."""


@pytest.fixture
def app(tmp_path: Path) -> Iterator[TemporaryApp]:
    with TemporaryApp(
        tmp_path,
        bundles=(SchedulerBundle, CacheBundle, LockBundle),
        modules={"message.restock_check": _MESSAGE, "scheduler.shop_schedule": _SHOP_SCHEDULE},
    ) as app:
        yield app


async def test_answers_write_a_provider_the_kernel_discovers(app: TemporaryApp) -> None:
    code, output = await app.run(
        ["make:schedule"], inputs=["report", "reports", "RestockCheck", "y", "y"]
    )

    assert code == ExitCode.SUCCESS, output
    module = app.import_generated("scheduler.report_schedule")
    provider_class = cast("type[ScheduleProviderInterface]", module.ReportSchedule)
    async with await app.boot() as booted:
        schedules = await booted.container.get(ScheduleProviderLocator)
        provider = await schedules.get("reports")
        schedule = provider.get_schedule()

    assert isinstance(provider, provider_class)
    assert len(schedule.recurring_messages) == 1
    assert schedule.get_state() is not None
    assert schedule.get_lock() is not None
    assert "messenger:consume scheduler_reports" in output


async def test_a_schedule_the_application_provides_is_refused(app: TemporaryApp) -> None:
    code, output = await app.run(["make:schedule", "Other", "--schedule", "shop", "-n"])

    assert code == ExitCode.INVALID
    assert "The schedule 'shop' is already provided by" in output


async def test_the_generated_file_passes_every_lint_rule_and_the_formatter(
    app: TemporaryApp,
) -> None:
    argv = ["make:schedule", "report", "--message", "RestockCheck", "--stateful", "--lock", "-n"]
    _ = await app.run(argv)
    path = str(app.package_dir / _GENERATED)

    checked = _ruff(app, "check", "--select", "ALL", "--ignore", _RUFF_IGNORED, path)
    formatted = _ruff(app, "format", "--check", path)

    assert checked.returncode == 0, checked.stdout
    assert formatted.returncode == 0, formatted.stdout


async def test_an_option_is_refused_without_its_bundle(tmp_path: Path) -> None:
    with TemporaryApp(tmp_path, bundles=(SchedulerBundle,)) as bare:
        code, output = await bare.run(["make:schedule", "report", "--stateful", "-n"])

    assert code == ExitCode.INVALID
    assert "--stateful needs the cache bundle" in output


async def test_the_maker_is_listed_with_the_scheduler_bundle(app: TemporaryApp) -> None:
    _, listed = await app.run(["list"])

    assert "make:schedule" in listed


async def test_the_maker_is_not_offered_without_the_scheduler_bundle(tmp_path: Path) -> None:
    with TemporaryApp(tmp_path) as bare:
        _, listed = await bare.run(["list"])

    assert "make:schedule" not in listed


def _ruff(app: TemporaryApp, *arguments: str) -> subprocess.CompletedProcess[str]:
    """Run the linter as an application would, with its defaults rather than this package's."""
    return subprocess.run(  # noqa: S603 — fixed arguments, the interpreter running the tests.
        [sys.executable, "-m", "ruff", *arguments, "--isolated"],
        cwd=app.project_dir,
        capture_output=True,
        text=True,
        check=False,
    )
