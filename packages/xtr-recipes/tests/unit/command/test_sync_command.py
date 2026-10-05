from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from xtr_console import ExitCode

from tests.support import (
    CONFIG,
    MESSENGER,
    MESSENGER_MANIFEST,
    RENDERED,
    build_project,
    build_tester,
    install_recipes,
    messenger_project,
    snapshot,
)

if TYPE_CHECKING:
    from pathlib import Path

    from xtr_console import ApplicationTester

pytestmark = pytest.mark.anyio

_BROKEN_BUNDLES = "BUNDLES = dict(**whatever())\n"


@pytest.fixture
def tester() -> ApplicationTester:
    return build_tester()


@pytest.fixture
def project_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    _ = messenger_project(tmp_path)
    install_recipes(monkeypatch, {MESSENGER: MESSENGER_MANIFEST})
    return tmp_path


def _argv(project_dir: Path, *options: str) -> list[str]:
    return ["recipes:sync", "--project-dir", str(project_dir), *options]


async def test_sync_applies_the_plan(tester: ApplicationTester, project_dir: Path) -> None:
    code = await tester.execute(_argv(project_dir))

    assert code == ExitCode.SUCCESS
    assert (project_dir / CONFIG).read_text(encoding="utf-8") == RENDERED


async def test_sync_reports_every_step_it_took(
    tester: ApplicationTester,
    project_dir: Path,
) -> None:
    _ = await tester.execute(_argv(project_dir))

    assert f"configure {MESSENGER}" in tester.display
    assert f"write {CONFIG}" in tester.display


async def test_a_second_sync_has_nothing_to_do(
    tester: ApplicationTester,
    project_dir: Path,
) -> None:
    _ = await tester.execute(_argv(project_dir))

    code = await tester.execute(_argv(project_dir))

    assert code == ExitCode.SUCCESS
    assert "nothing to do" in tester.display


async def test_check_fails_when_a_sync_would_change_the_project(
    tester: ApplicationTester,
    project_dir: Path,
) -> None:
    code = await tester.execute(_argv(project_dir, "--check"))

    assert code == ExitCode.FAILURE
    assert f"write {CONFIG}" in tester.display


async def test_check_writes_nothing(tester: ApplicationTester, project_dir: Path) -> None:
    before = snapshot(project_dir)

    _ = await tester.execute(_argv(project_dir, "--check"))

    assert snapshot(project_dir) == before


async def test_check_succeeds_when_the_project_is_in_sync(
    tester: ApplicationTester,
    project_dir: Path,
) -> None:
    _ = await tester.execute(_argv(project_dir))

    code = await tester.execute(_argv(project_dir, "--check"))

    assert code == ExitCode.SUCCESS
    assert "recipes are in sync" in tester.display


async def test_dry_run_prints_the_plan_and_writes_nothing(
    tester: ApplicationTester,
    project_dir: Path,
) -> None:
    before = snapshot(project_dir)

    code = await tester.execute(_argv(project_dir, "--dry-run"))

    assert code == ExitCode.SUCCESS
    assert f"write {CONFIG}" in tester.display
    assert snapshot(project_dir) == before


async def test_sync_reads_the_project_around_the_current_directory(
    tester: ApplicationTester,
    project_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(project_dir)

    code = await tester.execute(["recipes:sync"])

    assert code == ExitCode.SUCCESS
    assert (project_dir / CONFIG).is_file()


async def test_a_bundle_list_that_cannot_be_rewritten_is_reported(
    tester: ApplicationTester,
    project_dir: Path,
) -> None:
    _ = (project_dir / "src" / "app" / "bundles.py").write_text(_BROKEN_BUNDLES, encoding="utf-8")
    before = snapshot(project_dir)

    code = await tester.execute(_argv(project_dir))

    assert code == ExitCode.FAILURE
    assert "bundles.py" in tester.display
    assert snapshot(project_dir) == before


async def test_a_project_whose_package_is_missing_is_reported(
    tester: ApplicationTester,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_recipes(monkeypatch, {})
    _ = build_project(tmp_path)
    (tmp_path / "src" / "app" / "__init__.py").unlink()
    (tmp_path / "src" / "app").rmdir()

    code = await tester.execute(_argv(tmp_path))

    assert code == ExitCode.FAILURE
    assert "resolves to neither" in tester.display
