from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from xtr_console import ApplicationTester, ExitCode

from tests.support import build_tester, record_processes

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.anyio


@pytest.fixture
def tester() -> ApplicationTester:
    return build_tester()


async def test_init_makes_the_project_in_the_current_directory_keeping_its_repository(
    tester: ApplicationTester, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner = record_processes(monkeypatch)
    project = tmp_path / "my-tool"
    (project / ".git").mkdir(parents=True)
    monkeypatch.chdir(project)

    code = await tester.execute(["init", "--python", "3.13"])

    assert code == ExitCode.SUCCESS
    assert (project / "src" / "my_tool" / "kernel.py").is_file()
    assert all(argv[0] != "git" for argv, _ in runner.calls)
    assert "my-tool — the cli template" in tester.display
    assert "cd " not in tester.display


async def test_init_makes_a_web_application_under_a_name_other_than_the_directorys(
    tester: ApplicationTester, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _ = record_processes(monkeypatch)
    monkeypatch.chdir(tmp_path)

    code = await tester.execute(["init", "--name", "Billing API", "--webapp", "--python", "3.13"])

    assert code == ExitCode.SUCCESS
    assert (tmp_path / "src" / "billing_api" / "web" / "app.py").is_file()
    assert "billing-api — the webapp template" in tester.display
