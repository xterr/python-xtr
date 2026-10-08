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


async def test_new_makes_the_project_then_installs_and_syncs_it(
    tester: ApplicationTester, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner = record_processes(monkeypatch)
    target = tmp_path / "shop"

    code = await tester.execute(["new", str(target), "--python", "3.13"], interactive=False)

    assert code == ExitCode.SUCCESS
    assert (target / "src" / "shop" / "__main__.py").is_file()
    assert [argv[:3] for argv, _ in runner.calls] == [
        ("uv", "add", "--"),
        ("uv", "add", "--dev"),
        ("uv", "run", "xtr-recipes"),
        ("git", "init", "--quiet"),
    ]
    assert "shop is ready" in tester.display
    assert f"cd {target}" in tester.display
    assert "uv run shop app:hello" in tester.display


async def test_the_questions_fill_in_what_was_left_out(
    tester: ApplicationTester, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner = record_processes(monkeypatch)
    target = tmp_path / "web-shop"

    code = await tester.execute(
        ["new", "--python", "3.13", "--no-git"],
        inputs=[str(target), "webapp", "orm, security", "postgres", "y"],
    )

    assert code == ExitCode.SUCCESS
    assert "--template=webapp --with=orm:postgres,security --python=3.13 --no-git -n" in (
        tester.display
    )
    assert "xtr-orm[di,console,postgres]>=3.0,<4" in runner.calls[0][0]
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


async def test_declining_writes_nothing(
    tester: ApplicationTester, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner = record_processes(monkeypatch)

    code = await tester.execute(
        ["new", str(tmp_path / "shop"), "--template", "cli", "--with", "", "--python", "3.13"],
        inputs=["n"],
    )

    assert code == ExitCode.SUCCESS
    assert "Nothing was written" in tester.display
    assert runner.calls == []
    assert not (tmp_path / "shop").exists()


async def test_no_directory_is_an_invalid_command_line(
    tester: ApplicationTester, monkeypatch: pytest.MonkeyPatch
) -> None:
    _ = record_processes(monkeypatch)

    code = await tester.execute(["new"], interactive=False)

    assert code == ExitCode.INVALID
    assert "xtr new <directory>" in tester.display


@pytest.mark.parametrize(
    ("options", "message"),
    [
        (["--python", "3.10"], "give a version 3.11 or later"),
        (["--python", "three"], "give a version 3.11 or later"),
        (["--name", "json"], "would shadow the standard library"),
        (["--template", "nope"], "no template 'nope'"),
        (["--with", "queue"], "cannot add 'queue'"),
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
