"""``make:fixtures`` in an application: written through its console, then loaded by it."""

from __future__ import annotations

import subprocess
import sys
from typing import TYPE_CHECKING, cast

import pytest
from xtr_console import ExitCode
from xtr_orm.bundle import OrmBundle
from xtr_orm_fixtures import Fixture
from xtr_orm_fixtures.bundle import OrmFixturesBundle

from tests.support.temporary_app import TemporaryApp

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

pytestmark = pytest.mark.anyio

_RUFF_IGNORED = "CPY001,D203,D213,COM812,ISC001"
"""What an application selecting every rule turns off: no copyright header, the formatter's
conflicts, and one of each pair of docstring conventions that exclude each other."""

_ORM = '''"""One SQLite database, with table definitions of its own: none yet, nothing emptied."""

from __future__ import annotations

from sqlalchemy import MetaData
from xtr_dependency_injection import configure, env
from xtr_orm.bundle import ConnectionConfig, OrmConfig

METADATA = MetaData()


@configure
def orm() -> OrmConfig:
    return OrmConfig(
        connections={"default": ConnectionConfig(url=env("DATABASE_URL"), metadata=METADATA)}
    )
'''


@pytest.fixture
def app(tmp_path: Path) -> Iterator[TemporaryApp]:
    environ = {"DATABASE_URL": f"sqlite+aiosqlite:///{tmp_path / 'app.sqlite'}"}
    with TemporaryApp(
        tmp_path,
        bundles=(OrmBundle, OrmFixturesBundle),
        modules={"config.packages.orm": _ORM},
        environ=environ,
    ) as app:
        yield app


async def test_generated_class_is_a_fixture(app: TemporaryApp) -> None:
    code, output = await app.run(["make:fixtures", "AppFixtures", "-n"])
    assert code == ExitCode.SUCCESS, output

    generated = cast("type[object]", app.import_generated("fixtures.app_fixtures").AppFixtures)
    registered = {d.provider_qualname for d in app.kernel().build().report.definitions}

    assert issubclass(generated, Fixture)
    assert f"{app.package}.fixtures.app_fixtures:AppFixtures" in registered


async def test_the_generated_fixture_loads(app: TemporaryApp) -> None:
    code, output = await app.run(["make:fixtures", "catalog.BookFixtures", "-n"])
    assert code == ExitCode.SUCCESS, output

    code, output = await app.run(["orm:fixtures:load", "-n"], interactive=False)

    assert code == ExitCode.SUCCESS, output
    assert f"loading {app.package}.fixtures.catalog.book_fixtures.BookFixtures" in output
    assert "Loaded 1 fixture." in output


async def test_not_registered_without_the_fixtures_bundle(tmp_path: Path) -> None:
    with TemporaryApp(tmp_path, bundles=(OrmBundle,)) as app:
        _, listed = await app.run(["list"])

    assert "make:fixtures" not in listed
    assert "make:entity" in listed


async def test_the_generated_file_passes_every_lint_rule_and_the_formatter(
    app: TemporaryApp,
) -> None:
    code, output = await app.run(["make:fixtures", "LintFixtures", "-n"])
    assert code == ExitCode.SUCCESS, output
    path = str(app.package_dir / "fixtures" / "lint_fixtures.py")

    checked = _ruff(app, "check", "--select", "ALL", "--ignore", _RUFF_IGNORED, path)
    formatted = _ruff(app, "format", "--check", path)

    assert checked.returncode == 0, checked.stdout
    assert formatted.returncode == 0, formatted.stdout


def _ruff(app: TemporaryApp, *arguments: str) -> subprocess.CompletedProcess[str]:
    """Run the linter as an application would, with its defaults rather than this package's."""
    return subprocess.run(  # noqa: S603 — fixed arguments, the interpreter running the tests.
        [sys.executable, "-m", "ruff", *arguments, "--isolated"],
        cwd=app.project_dir,
        capture_output=True,
        text=True,
        check=False,
    )
