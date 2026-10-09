from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from xtr_console import ApplicationTester, ExitCode

from tests.support import build_tester, record_runs, write_project
from xtr_cli.subprocess_runner import NOT_FOUND

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.anyio

_SERVER = "import uvicorn\n"
_APP = "from fastapi import FastAPI\n\napp = FastAPI()\n"


@pytest.fixture
def tester() -> ApplicationTester:
    return build_tester()


def _web_project(directory: Path) -> Path:
    return write_project(
        directory, {"shop-web": "shop.web.__main__:main"}, {"src/shop/web/__main__.py": _SERVER}
    )


async def test_serve_runs_the_web_script_in_the_project_reloading_by_default(
    tester: ApplicationTester, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner = record_runs(monkeypatch)
    project = _web_project(tmp_path / "shop")
    monkeypatch.chdir(project / "src" / "shop")

    code = await tester.execute(["serve"], interactive=False)

    assert code == ExitCode.SUCCESS
    assert runner.calls == [(("uv", "run", "shop-web"), project)]
    assert runner.environments == [{"WEB_RELOAD": "1"}]
    assert "WEB_RELOAD=1 uv run shop-web" in tester.display


async def test_host_port_and_no_reload_reach_the_script(
    tester: ApplicationTester, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner = record_runs(monkeypatch)
    project = _web_project(tmp_path)

    code = await tester.execute(
        [
            "serve",
            "--project-dir",
            str(project),
            "--host",
            "10.0.0.5",
            "--port",
            "9000",
            "--no-reload",
        ],
        interactive=False,
    )

    assert code == ExitCode.SUCCESS
    assert runner.environments == [{"WEB_HOST": "10.0.0.5", "WEB_PORT": "9000"}]


async def test_an_asgi_object_is_served_with_uvicorn(
    tester: ApplicationTester, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner = record_runs(monkeypatch)
    project = write_project(tmp_path, {}, {"src/shop/app.py": _APP})

    code = await tester.execute(["serve", "--project-dir", str(project)], interactive=False)

    assert code == ExitCode.SUCCESS
    assert runner.calls[0][0] == (
        "uv", "run", "uvicorn", "shop.app:app", "--host", "127.0.0.1", "--port", "8000", "--reload",
    )  # fmt: skip


async def test_a_dry_run_prints_the_command_and_runs_nothing(
    tester: ApplicationTester, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner = record_runs(monkeypatch)

    code = await tester.execute(
        ["serve", "--project-dir", str(_web_project(tmp_path)), "--dry-run"], interactive=False
    )

    assert code == ExitCode.SUCCESS
    assert "Serving shop-web from" in tester.display
    assert runner.calls == []


async def test_the_entrypoint_option_wins_over_detection(
    tester: ApplicationTester, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner = record_runs(monkeypatch)
    project = _web_project(tmp_path)

    code = await tester.execute(
        ["serve", "--project-dir", str(project), "--entrypoint", "shop.web.app:app"],
        interactive=False,
    )

    assert code == ExitCode.SUCCESS
    assert runner.calls[0][0][2:4] == ("uvicorn", "shop.web.app:app")


async def test_several_entry_points_are_asked_about(
    tester: ApplicationTester, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner = record_runs(monkeypatch)
    project = write_project(tmp_path, {}, {"a.py": _APP, "b.py": _APP})

    code = await tester.execute(["serve", "--project-dir", str(project)], inputs=["b:app"])

    assert code == ExitCode.SUCCESS
    assert runner.calls[0][0][3] == "b:app"


async def test_several_entry_points_with_no_question_possible_are_refused(
    tester: ApplicationTester, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner = record_runs(monkeypatch)
    project = write_project(tmp_path, {}, {"a.py": _APP, "b.py": _APP})

    code = await tester.execute(["serve", "--project-dir", str(project)], interactive=False)

    assert code == ExitCode.FAILURE
    assert "several web entry points (a:app, b:app)" in tester.display
    assert runner.calls == []


async def test_nothing_to_serve_says_how_to_name_it(
    tester: ApplicationTester, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _ = record_runs(monkeypatch)
    project = write_project(tmp_path, {"shop": "shop:main"}, {})

    code = await tester.execute(["serve", "--project-dir", str(project)], interactive=False)

    assert code == ExitCode.FAILURE
    assert "pass --entrypoint" in tester.display


async def test_the_servers_exit_code_is_the_commands(
    tester: ApplicationTester, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _ = record_runs(monkeypatch, 3)

    code = await tester.execute(
        ["serve", "--project-dir", str(_web_project(tmp_path))], interactive=False
    )

    assert code == 3


async def test_a_missing_uv_is_named(
    tester: ApplicationTester, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _ = record_runs(monkeypatch, NOT_FOUND)

    code = await tester.execute(
        ["serve", "--project-dir", str(_web_project(tmp_path))], interactive=False
    )

    assert code == NOT_FOUND
    assert "uv is not on the PATH" in tester.display


async def test_a_port_out_of_range_is_refused(tester: ApplicationTester, tmp_path: Path) -> None:
    code = await tester.execute(
        ["serve", "--project-dir", str(_web_project(tmp_path)), "--port", "70000"],
        interactive=False,
    )

    assert code == ExitCode.INVALID
