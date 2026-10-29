from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from cryptography.hazmat.primitives.serialization import load_pem_private_key
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
from xtr_recipes.marked_block_editor import MarkedBlockEditor

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
    (tmp_path / "src" / "app" / "kernel.py").unlink()

    code = await tester.execute(_argv(tmp_path))

    assert code == ExitCode.FAILURE
    assert "no kernel.py was found" in tester.display


_KEYED_MANIFEST = """\
[env]
KEY_PATH = "%kernel.project_dir%/secrets/server.pem"
KEY_PASSPHRASE = "%generate(secret)%"

[keys]
"secrets/server.pem" = { algorithm = "ES256", passphrase = "KEY_PASSPHRASE" }
"""


async def test_sync_mints_a_key_sealed_with_the_secret_it_writes(
    tester: ApplicationTester,
    project_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_recipes(monkeypatch, {MESSENGER: _KEYED_MANIFEST})

    code = await tester.execute(_argv(project_dir))

    env = (project_dir / ".env").read_text(encoding="utf-8")
    passphrase = MarkedBlockEditor().env_value(env, "KEY_PASSPHRASE")
    key = (project_dir / "secrets" / "server.pem").read_bytes()
    assert code == ExitCode.SUCCESS
    assert "mint secrets/server.pem (ES256)" in tester.display
    assert passphrase is not None
    assert load_pem_private_key(key, passphrase.encode()) is not None


async def test_a_second_sync_keeps_the_minted_key(
    tester: ApplicationTester,
    project_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_recipes(monkeypatch, {MESSENGER: _KEYED_MANIFEST})
    _ = await tester.execute(_argv(project_dir))
    before = snapshot(project_dir)

    _ = await tester.execute(["recipes:install", MESSENGER, "--project-dir", str(project_dir)])

    assert snapshot(project_dir) == before
    assert "kept secrets/server.pem (in place)" in tester.display
