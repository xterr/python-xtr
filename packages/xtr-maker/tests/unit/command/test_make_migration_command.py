"""Unit tests for :class:`xtr_maker.command.make_migration_command.MakeMigrationCommand`.

Each runs against a real migrator over a SQLite file under the test's directory:
building one costs nothing, and a fake would only restate what it answers.
"""

from __future__ import annotations

from pathlib import PurePath
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import Column, Integer, MetaData, String, Table
from sqlalchemy.ext.asyncio import create_async_engine
from xtr_console import ExitCode
from xtr_orm import ConnectionRegistry, DatabaseManager, MigrationsConfig, Migrator

from tests.support.captured_style import CapturedStyle
from xtr_maker import FileManager
from xtr_maker.command.make_migration_command import MakeMigrationCommand

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from pathlib import Path

    from sqlalchemy.ext.asyncio import AsyncEngine

pytestmark = pytest.mark.anyio

_HINT = "Run orm:migrations:migrate -n first."


def _books() -> MetaData:
    metadata = MetaData()
    _ = Table(
        "book",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("title", String(200), nullable=False),
    )
    return metadata


@pytest.fixture
def project(tmp_path: Path) -> Path:
    return tmp_path / "project"


@pytest.fixture
async def engine(tmp_path: Path) -> AsyncIterator[AsyncEngine]:
    built = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'app.sqlite'}")
    yield built
    await built.dispose()


def _migrator(engine: AsyncEngine, directory: Path, metadata: MetaData | None = None) -> Migrator:
    return Migrator(engine, MigrationsConfig(directory=str(directory)), metadata)


def _command(project: Path, migrator: Migrator) -> MakeMigrationCommand:
    registry = ConnectionRegistry()
    registry.register(
        "default",
        engine=migrator.engine,
        migrator=migrator,
        database=DatabaseManager("sqlite+aiosqlite://"),
    )
    return MakeMigrationCommand(registry, FileManager(project, "app"))


def _revisions(directory: Path) -> list[str]:
    return sorted(path.name for path in directory.glob("*.py")) if directory.is_dir() else []


async def test_a_revision_is_written_and_its_path_shown_from_the_project(
    project: Path, engine: AsyncEngine
) -> None:
    directory = project / "migrations"
    style = CapturedStyle(interactive=False)

    code = await _command(project, _migrator(engine, directory, _books()))(
        style.io, message="add books"
    )

    assert code == ExitCode.SUCCESS, style.output
    [written] = _revisions(directory)
    assert written.endswith("_add_books.py")
    assert f"created: migrations/{written}" in style.lines
    assert style.lines[-2:] == [
        "Next:",
        "- Review the new revision, then run orm:migrations:migrate -n.",
    ]


async def test_the_message_is_asked_when_left_out(project: Path, engine: AsyncEngine) -> None:
    directory = project / "migrations"

    code = await _command(project, _migrator(engine, directory, _books()))(
        CapturedStyle(["create the book table"]).io
    )

    assert code == ExitCode.SUCCESS
    [written] = _revisions(directory)
    assert written.endswith("_create_the_book_table.py")


async def test_without_a_terminal_the_message_is_auto(project: Path, engine: AsyncEngine) -> None:
    directory = project / "migrations"

    code = await _command(project, _migrator(engine, directory, _books()))(
        CapturedStyle(interactive=False).io
    )

    assert code == ExitCode.SUCCESS
    [written] = _revisions(directory)
    assert written.endswith("_auto.py")


async def test_an_empty_message_is_refused(project: Path, engine: AsyncEngine) -> None:
    directory = project / "migrations"
    style = CapturedStyle(interactive=False)

    code = await _command(project, _migrator(engine, directory, _books()))(style.io, message=" ")

    assert code == ExitCode.INVALID
    assert "The revision's message cannot be empty." in style.output
    assert _revisions(directory) == []


async def test_nothing_is_written_when_nothing_differs(project: Path, engine: AsyncEngine) -> None:
    directory = project / "migrations"
    style = CapturedStyle(interactive=False)

    code = await _command(project, _migrator(engine, directory, MetaData()))(style.io)

    assert code == ExitCode.SUCCESS
    assert "No database changes were detected." in style.output
    assert _revisions(directory) == []


async def test_a_database_behind_its_revisions_is_refused_naming_the_fix(
    project: Path, engine: AsyncEngine
) -> None:
    directory = project / "migrations"
    migrator = _migrator(engine, directory, _books())
    pending = migrator.generate("pending")
    style = CapturedStyle(interactive=False)

    code = await _command(project, migrator)(style.io)

    assert code == ExitCode.FAILURE
    assert "The database is behind its revisions: 1 revision is not applied." in style.output
    assert style.lines[-1] == _HINT
    assert _revisions(directory) == [PurePath(pending.path).name]


async def test_several_revisions_behind_are_counted(project: Path, engine: AsyncEngine) -> None:
    directory = project / "migrations"
    migrator = _migrator(engine, directory, _books())
    _ = migrator.generate("first")
    _ = migrator.generate("second")
    style = CapturedStyle(interactive=False)

    code = await _command(project, migrator)(style.io)

    assert code == ExitCode.FAILURE
    assert "2 revisions are not applied." in style.output


async def test_another_migration_error_is_reported_by_its_reason(
    project: Path, engine: AsyncEngine
) -> None:
    style = CapturedStyle(interactive=False)

    code = await _command(project, _migrator(engine, project / "migrations"))(style.io)

    assert code == ExitCode.FAILURE
    assert 'The "default" connection has no table definitions to compare with.' in style.output
    assert _HINT not in style.output


async def test_an_unknown_connection_is_refused_naming_the_registered_ones(
    project: Path, engine: AsyncEngine
) -> None:
    directory = project / "migrations"
    style = CapturedStyle(interactive=False)

    code = await _command(project, _migrator(engine, directory, _books()))(
        style.io, connection="reports"
    )

    assert code == ExitCode.INVALID
    assert 'Unknown connection "reports"; the connections are: "default".' in style.output
    assert _revisions(directory) == []


async def test_a_revision_outside_the_project_is_shown_by_its_own_path(
    tmp_path: Path, project: Path, engine: AsyncEngine
) -> None:
    directory = tmp_path / "elsewhere"
    style = CapturedStyle(interactive=False)

    code = await _command(project, _migrator(engine, directory, _books()))(style.io)

    assert code == ExitCode.SUCCESS
    [written] = _revisions(directory)
    assert f"created: {directory / written}" in style.lines
