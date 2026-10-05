from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from xtr_console import ExitCode

from tests.support import (
    CONFIG,
    MESSENGER,
    MESSENGER_MANIFEST,
    RENDERED,
    build_tester,
    install_recipes,
    messenger_project,
)

if TYPE_CHECKING:
    from pathlib import Path

    from xtr_console import ApplicationTester

pytestmark = pytest.mark.anyio

_EDITED = "MESSENGER = mine\n"


@pytest.fixture
def tester() -> ApplicationTester:
    return build_tester()


@pytest.fixture
def project_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    _ = messenger_project(tmp_path)
    install_recipes(monkeypatch, {MESSENGER: MESSENGER_MANIFEST})
    return tmp_path


def _argv(project_dir: Path, package: str, *options: str) -> list[str]:
    return ["recipes:install", package, "--project-dir", str(project_dir), *options]


async def test_install_applies_one_package(
    tester: ApplicationTester,
    project_dir: Path,
) -> None:
    code = await tester.execute(_argv(project_dir, MESSENGER))

    assert code == ExitCode.SUCCESS
    assert (project_dir / CONFIG).read_text(encoding="utf-8") == RENDERED


async def test_install_restores_a_file_that_went_missing(
    tester: ApplicationTester,
    project_dir: Path,
) -> None:
    _ = await tester.execute(["recipes:sync", "--project-dir", str(project_dir)])
    (project_dir / CONFIG).unlink()

    code = await tester.execute(_argv(project_dir, MESSENGER))

    assert code == ExitCode.SUCCESS
    assert (project_dir / CONFIG).read_text(encoding="utf-8") == RENDERED


async def test_install_leaves_an_edited_file_and_offers_the_new_content_beside_it(
    tester: ApplicationTester,
    project_dir: Path,
) -> None:
    _ = await tester.execute(["recipes:sync", "--project-dir", str(project_dir)])
    _ = (project_dir / CONFIG).write_text(_EDITED, encoding="utf-8")

    code = await tester.execute(_argv(project_dir, MESSENGER))

    assert code == ExitCode.SUCCESS
    assert (project_dir / CONFIG).read_text(encoding="utf-8") == _EDITED
    assert (project_dir / f"{CONFIG}.new").read_text(encoding="utf-8") == RENDERED


async def test_install_force_overwrites_an_edited_file(
    tester: ApplicationTester,
    project_dir: Path,
) -> None:
    _ = await tester.execute(["recipes:sync", "--project-dir", str(project_dir)])
    _ = (project_dir / CONFIG).write_text(_EDITED, encoding="utf-8")

    code = await tester.execute(_argv(project_dir, MESSENGER, "--force"))

    assert code == ExitCode.SUCCESS
    assert (project_dir / CONFIG).read_text(encoding="utf-8") == RENDERED
    assert not (project_dir / f"{CONFIG}.new").exists()


async def test_install_normalises_the_package_name(
    tester: ApplicationTester,
    project_dir: Path,
) -> None:
    code = await tester.execute(_argv(project_dir, "XTR_Messenger"))

    assert code == ExitCode.SUCCESS
    assert (project_dir / CONFIG).is_file()


async def test_install_reports_a_package_with_no_recipe(
    tester: ApplicationTester,
    project_dir: Path,
) -> None:
    code = await tester.execute(_argv(project_dir, "xtr-nothing"))

    assert code == ExitCode.FAILURE
    assert "xtr-nothing has no recipe to apply" in tester.display
