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


async def test_new_makes_a_console_application_then_installs_and_syncs_it_asking_nothing(
    tester: ApplicationTester, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner = record_processes(monkeypatch)
    target = tmp_path / "shop"

    code = await tester.execute(["new", str(target), "--python", "3.13"])

    assert code == ExitCode.SUCCESS
    assert (target / "src" / "shop" / "__main__.py").is_file()
    assert not (target / "src" / "shop" / "web").exists()
    assert [argv[:3] for argv, _ in runner.calls] == [
        ("uv", "add", "--"),
        ("uv", "add", "--dev"),
        ("uv", "run", "xtr-recipes"),
        ("git", "init", "--quiet"),
    ]
    assert "shop is ready" in tester.display
    assert f"cd {target}" in tester.display
    assert "uv run shop app:hello" in tester.display


async def test_webapp_makes_a_web_application_with_the_web_packages(
    tester: ApplicationTester, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner = record_processes(monkeypatch)
    target = tmp_path / "web-shop"

    code = await tester.execute(["new", str(target), "--webapp", "--python", "3.13", "--no-git"])

    assert code == ExitCode.SUCCESS
    assert "the webapp template" in tester.display
    assert "xtr-orm[postgres]>=3.0,<4" in runner.calls[0][0]
    assert "xtr-security>=3.0,<4" in runner.calls[0][0]
    assert all(argv[0] != "git" for argv, _ in runner.calls)
    assert (target / "src" / "web_shop" / "web" / "app.py").is_file()


async def test_a_dry_run_prints_the_plan_and_writes_nothing(
    tester: ApplicationTester, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner = record_processes(monkeypatch)

    code = await tester.execute(
        ["new", str(tmp_path / "shop"), "--dry-run", "--python", "3.13"], interactive=False
    )

    assert code == ExitCode.SUCCESS
    assert "write src/shop/kernel.py" in tester.display
    assert "run   uv run xtr-recipes recipes:sync" in tester.display
    assert runner.calls == []
    assert not (tmp_path / "shop").exists()


async def test_no_directory_is_an_invalid_command_line(
    tester: ApplicationTester, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner = record_processes(monkeypatch)

    code = await tester.execute(["new"])

    assert code == ExitCode.INVALID
    assert "DIRECTORY requires an argument" in tester.error_display
    assert runner.calls == []


@pytest.mark.parametrize(
    ("options", "message"),
    [
        (["--python", "3.10"], "give a version 3.11 or later"),
        (["--python", "three"], "give a version 3.11 or later"),
        (["--name", "json"], "would shadow the standard library"),
    ],
)
async def test_a_setting_it_cannot_use_fails_before_anything_is_written(
    tester: ApplicationTester,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    options: list[str],
    message: str,
) -> None:
    runner = record_processes(monkeypatch)

    code = await tester.execute(["new", str(tmp_path / "shop"), *options], interactive=False)

    assert code == ExitCode.FAILURE
    assert message in tester.display
    assert runner.calls == []
    assert not (tmp_path / "shop").exists()


async def test_a_directory_in_use_is_refused(
    tester: ApplicationTester, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _ = record_processes(monkeypatch)
    _ = (tmp_path / "notes.txt").write_text("mine", encoding="utf-8")

    code = await tester.execute(["new", str(tmp_path), "--python", "3.13"], interactive=False)

    assert code == ExitCode.FAILURE
    assert "is not empty (notes.txt)" in tester.display


async def test_a_failing_step_is_reported_with_the_command(
    tester: ApplicationTester, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _ = record_processes(monkeypatch, 1)

    code = await tester.execute(
        ["new", str(tmp_path / "shop"), "--python", "3.13"], interactive=False
    )

    assert code == ExitCode.FAILURE
    assert "exited with 1" in tester.display
    assert "shop is ready" not in tester.display
