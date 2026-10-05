from __future__ import annotations

from typing import TYPE_CHECKING, final

import pytest
from xtr_console import ExitCode
from xtr_dependency_injection import Bundle, as_bundle

from tests.support import (
    MESSENGER,
    MESSENGER_MANIFEST,
    TARGET,
    TEMPLATE,
    build_tester,
    install_recipes,
    messenger_project,
    snapshot,
)

if TYPE_CHECKING:
    from pathlib import Path

    from xtr_console import ApplicationTester

pytestmark = pytest.mark.anyio


@final
@as_bundle("show_messenger")
class MessengerBundle(Bundle):
    pass


_FULL_MANIFEST = f"""\
[bundles]
"{TARGET}" = {{ all = true }}

[files]
"config/messenger.py" = "{TEMPLATE}"

[env]
MESSENGER_DSN = ""

[gitignore]
lines = ["/var/messenger"]

[notes]
steps = ["call setup(app, kernel)"]
check = ["<script> debug:bundles"]
"""
_CHANGED_MANIFEST = f'[files]\n"config/messenger.py" = "{TEMPLATE}"\n'


@pytest.fixture
def tester() -> ApplicationTester:
    return build_tester()


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    _ = messenger_project(tmp_path)
    return tmp_path


def _argv(project_dir: Path, *arguments: str) -> list[str]:
    return ["recipes:show", *arguments, "--project-dir", str(project_dir)]


async def test_show_says_so_when_no_recipe_is_installed(
    tester: ApplicationTester,
    project_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_recipes(monkeypatch, {})

    code = await tester.execute(_argv(project_dir))

    assert code == ExitCode.SUCCESS
    assert "no recipes installed" in tester.display


async def test_show_writes_nothing(
    tester: ApplicationTester,
    project_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_recipes(monkeypatch, {MESSENGER: MESSENGER_MANIFEST})
    before = snapshot(project_dir)

    _ = await tester.execute(_argv(project_dir))

    assert snapshot(project_dir) == before


async def test_show_lists_a_recipe_the_lock_has_never_recorded(
    tester: ApplicationTester,
    project_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_recipes(monkeypatch, {MESSENGER: MESSENGER_MANIFEST})

    code = await tester.execute(_argv(project_dir))

    assert code == ExitCode.SUCCESS
    assert "not configured" in tester.display


async def test_show_lists_a_recipe_that_has_been_applied(
    tester: ApplicationTester,
    project_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_recipes(monkeypatch, {MESSENGER: MESSENGER_MANIFEST})
    _ = await tester.execute(["recipes:sync", "--project-dir", str(project_dir)])

    _ = await tester.execute(_argv(project_dir))

    assert "locked" in tester.display


async def test_show_lists_a_recipe_whose_content_has_moved_on(
    tester: ApplicationTester,
    project_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_recipes(monkeypatch, {MESSENGER: MESSENGER_MANIFEST})
    _ = await tester.execute(["recipes:sync", "--project-dir", str(project_dir)])
    install_recipes(monkeypatch, {MESSENGER: _CHANGED_MANIFEST})

    _ = await tester.execute(_argv(project_dir))

    assert "outdated" in tester.display


async def test_show_lists_a_package_whose_bundle_class_is_not_there(
    tester: ApplicationTester,
    project_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_recipes(monkeypatch, {MESSENGER: _FULL_MANIFEST})

    _ = await tester.execute(_argv(project_dir))

    assert f"skipped: install {MESSENGER}[di]" in tester.display


async def test_show_lists_a_locked_package_that_is_no_longer_installed(
    tester: ApplicationTester,
    project_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_recipes(monkeypatch, {MESSENGER: MESSENGER_MANIFEST})
    _ = await tester.execute(["recipes:sync", "--project-dir", str(project_dir)])
    install_recipes(monkeypatch, {})

    _ = await tester.execute(_argv(project_dir))

    assert "removed" in tester.display


async def test_show_reads_one_recipe_in_full(
    tester: ApplicationTester,
    project_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_recipes(monkeypatch, {MESSENGER: _FULL_MANIFEST}, {TARGET: MessengerBundle})

    code = await tester.execute(_argv(project_dir, MESSENGER))

    assert code == ExitCode.SUCCESS
    assert tester.display.splitlines() == [
        "",
        MESSENGER,
        "-" * len(MESSENGER),
        "",
        "  bundles:",
        f"    - {TARGET} all=true",
        "  files:",
        f"    - config/messenger.py ← {TEMPLATE}",
        "  env:",
        "    - MESSENGER_DSN",
        "  gitignore:",
        "    - /var/messenger",
        "  steps:",
        "    - call setup(app, kernel)",
        "  check:",
        "    - <script> debug:bundles",
    ]


async def test_show_normalises_the_package_name(
    tester: ApplicationTester,
    project_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_recipes(monkeypatch, {MESSENGER: MESSENGER_MANIFEST})

    code = await tester.execute(_argv(project_dir, "XTR_Messenger"))

    assert code == ExitCode.SUCCESS
    assert "- MESSENGER_DSN" in tester.display


async def test_show_reports_a_package_with_no_recipe(
    tester: ApplicationTester,
    project_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_recipes(monkeypatch, {MESSENGER: MESSENGER_MANIFEST})

    code = await tester.execute(_argv(project_dir, "xtr-nothing"))

    assert code == ExitCode.FAILURE
    assert "xtr-nothing has no recipe to apply" in tester.display
