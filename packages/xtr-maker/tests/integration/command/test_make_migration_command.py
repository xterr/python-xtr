"""``make:migration`` in an application: run through its console against a SQLite database."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from xtr_console import ExitCode
from xtr_orm.bundle import OrmBundle

from tests.support.temporary_app import TemporaryApp

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

pytestmark = pytest.mark.anyio

_BASE = '''"""The table definitions every model of the application shares."""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
'''

_BOOK = '''"""A book."""

from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Book(Base):
    __tablename__ = "book"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
'''

_AUTHOR = '''"""An author."""

from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Author(Base):
    __tablename__ = "author"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
'''

_ORM = '''"""One SQLite database, compared with the application's own table definitions."""

from __future__ import annotations

from xtr_dependency_injection import configure
from xtr_orm.bundle import ConnectionConfig, MigrationsConfig, OrmConfig

from ...entity.base import Base


@configure
def orm() -> OrmConfig:
    return OrmConfig(
        connections={{
            "default": ConnectionConfig(
                url="sqlite+aiosqlite:///{database}",
                metadata=Base.metadata,
                migrations=MigrationsConfig(
                    directory="%kernel.project_dir%/migrations", render_as_batch=True
                ),
            ),
        }},
    )
'''

_HINT = "Run orm:migrations:migrate -n first."


@pytest.fixture
def app(tmp_path: Path) -> Iterator[TemporaryApp]:
    with TemporaryApp(
        tmp_path,
        bundles=(OrmBundle,),
        modules={
            "entity.base": _BASE,
            "entity.book": _BOOK,
            "config.packages.orm": _ORM.format(database=tmp_path / "app.sqlite"),
        },
    ) as app:
        yield app


def _revisions(app: TemporaryApp) -> list[str]:
    directory = app.project_dir / "migrations"
    return sorted(path.name for path in directory.glob("*.py")) if directory.is_dir() else []


async def test_a_revision_is_written_for_a_new_model(app: TemporaryApp) -> None:
    code, output = await app.run(["make:migration", "--message", "add books", "-n"])

    assert code == ExitCode.SUCCESS, output
    [written] = _revisions(app)
    assert written.endswith("_add_books.py")
    assert f"created: migrations/{written}" in output
    source = (app.project_dir / "migrations" / written).read_text(encoding="utf-8")
    assert "op.create_table(" in source
    assert "book" in source


async def test_a_migrated_database_has_no_changes_to_write(app: TemporaryApp) -> None:
    _ = await app.run(["make:migration", "-n"])
    migrated, migrate_output = await app.run(["orm:migrations:migrate", "-n"])

    code, output = await app.run(["make:migration", "-n"])

    assert migrated == ExitCode.SUCCESS, migrate_output
    assert code == ExitCode.SUCCESS, output
    assert "No database changes were detected." in output
    assert len(_revisions(app)) == 1


async def test_a_pending_revision_must_be_migrated_first(app: TemporaryApp) -> None:
    _ = await app.run(["make:migration", "-n"])
    _ = await app.run(["orm:migrations:migrate", "-n"])
    _ = (app.package_dir / "entity" / "author.py").write_text(_AUTHOR, encoding="utf-8")
    written, written_output = await app.run(["make:migration", "--message", "add authors", "-n"])

    code, output = await app.run(["make:migration", "-n"])

    assert written == ExitCode.SUCCESS, written_output
    assert code == ExitCode.FAILURE
    assert "The database is behind its revisions: 1 revision is not applied." in output
    assert _HINT in output
    assert len(_revisions(app)) == 2


async def test_the_maker_is_listed_with_the_orm_bundle(app: TemporaryApp) -> None:
    _, listed = await app.run(["list"])

    assert "make:migration" in listed


async def test_the_maker_is_not_offered_without_the_orm_bundle(tmp_path: Path) -> None:
    with TemporaryApp(tmp_path) as bare:
        _, listed = await bare.run(["list"])

    assert "make:migration" not in listed
