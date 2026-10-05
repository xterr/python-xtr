from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from xtr_console import ExitCode

from tests.support import build_tester, messenger_project, record_processes

if TYPE_CHECKING:
    from pathlib import Path

    from xtr_console import ApplicationTester

pytestmark = pytest.mark.anyio

_REQUIREMENT = "xtr-clock[di]"
_UV_FAILED = 2
_SYNC_CODE = 7


@pytest.fixture
def tester() -> ApplicationTester:
    return build_tester()


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    _ = messenger_project(tmp_path)
    return tmp_path


def _argv(project_dir: Path) -> list[str]:
    return ["recipes:add", _REQUIREMENT, "--project-dir", str(project_dir)]


async def test_add_installs_the_requirement_then_syncs_in_a_fresh_process(
    tester: ApplicationTester,
    project_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorder = record_processes(monkeypatch, 0, _SYNC_CODE)

    code = await tester.execute(_argv(project_dir))

    assert recorder.calls == [
        (("uv", "add", _REQUIREMENT), project_dir),
        (
            ("uv", "run", "xtr-recipes", "recipes:sync", "--project-dir", str(project_dir)),
            project_dir,
        ),
    ]
    assert code == _SYNC_CODE


async def test_add_stops_before_the_sync_when_the_install_failed(
    tester: ApplicationTester,
    project_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorder = record_processes(monkeypatch, _UV_FAILED)

    code = await tester.execute(_argv(project_dir))

    assert recorder.calls == [(("uv", "add", _REQUIREMENT), project_dir)]
    assert code == ExitCode.FAILURE
    assert f"uv add {_REQUIREMENT} failed" in tester.display


async def test_add_reports_a_project_it_cannot_resolve(
    tester: ApplicationTester,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorder = record_processes(monkeypatch, 0, 0)
    _ = (tmp_path / "pyproject.toml").write_text('[project]\nname = "ghost"\n', encoding="utf-8")

    code = await tester.execute(["recipes:add", _REQUIREMENT, "--project-dir", str(tmp_path)])

    assert code == ExitCode.FAILURE
    assert recorder.calls == []
