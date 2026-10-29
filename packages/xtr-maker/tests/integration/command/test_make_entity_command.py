"""``make:entity`` in an application: run through its console, then mapped, migrated and used."""

from __future__ import annotations

import subprocess
import sys
from decimal import Decimal
from typing import TYPE_CHECKING, cast

import pytest
from advanced_alchemy.base import UUIDAuditBase, orm_registry
from advanced_alchemy.repository import SQLAlchemyAsyncRepository
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.orm import configure_mappers
from xtr_console import ExitCode
from xtr_dependency_injection import unit_of_work
from xtr_orm.bundle import OrmBundle

from tests.support.temporary_app import TemporaryApp

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator
    from pathlib import Path

pytestmark = pytest.mark.anyio

_DATABASE = '''"""One SQLite database under the test's directory."""

from __future__ import annotations

from xtr_dependency_injection import configure
from xtr_orm.bundle import ConnectionConfig, OrmConfig


@configure
def orm() -> OrmConfig:
    return OrmConfig(connections={{"default": ConnectionConfig(url="sqlite+aiosqlite:///{path}")}})
'''

_AUTHOR = ["make:entity", "Author", "--field", "name:string:120", "-n"]
_BOOK = [
    "make:entity",
    "Book",
    "--field",
    "title:string:120",
    "--field",
    "price:decimal:10:2",
    "--field",
    "published_at:datetime?",
    "--relation",
    "author:many_to_one:Author,inverse=books",
    "-n",
]
_GENERATED = (
    "entity/author.py",
    "entity/book.py",
    "repository/author_repository.py",
    "repository/book_repository.py",
    "entity/tag.py",
    "entity/review.py",
)
_EVERY_TYPE = [
    "make:entity",
    "Parcel",
    "--field",
    "label:string:40",
    "--field",
    "notes:text?",
    "--field",
    "count:integer",
    "--field",
    "serial:big_integer",
    "--field",
    "rank:small_integer",
    "--field",
    "is_fragile:boolean",
    "--field",
    "weight:float",
    "--field",
    "price:decimal:8:3",
    "--field",
    "sent_on:date",
    "--field",
    "sent_at:datetime",
    "--field",
    "slot:time",
    "--field",
    "details:json",
    "--field",
    "tracking_id:uuid",
    "--field",
    "status:enum:http.HTTPStatus",
    "--field",
    "scan:binary?",
    "-n",
]
"""One field of every type ``make:entity`` writes."""

_RUFF_IGNORED = "CPY001,D203,D213,COM812,ISC001,TC001,TC002,TC003"
"""What an application selecting every rule turns off: no copyright header, the formatter's
conflicts, one of each pair of docstring conventions that exclude each other — and moving
imports under TYPE_CHECKING, since the mapper reads column annotations and the container
reads factory annotations at runtime."""


@pytest.fixture(autouse=True)
def _forget_mapped_entities() -> Iterator[None]:
    """Unmap what a test mapped: every entity of every run shares the base's registry."""
    before = frozenset(orm_registry.metadata.tables)
    yield
    _unmap(before)


def _unmap(kept: frozenset[str]) -> None:
    """Forget every mapped class, and every table but ``kept``."""
    orm_registry.dispose()
    for name in set(orm_registry.metadata.tables) - kept:
        orm_registry.metadata.remove(orm_registry.metadata.tables[name])


def _restart(app: TemporaryApp, kept: frozenset[str]) -> None:
    """Forget what the console runs imported, as the next process would.

    Each run boots the kernel, which imports the entities written so far: an
    entity a later run edited would otherwise stay mapped as it was before.
    """
    _unmap(kept)
    prefix = f"{app.package}."
    for name in [name for name in sys.modules if name.startswith(prefix)]:
        del sys.modules[name]


@pytest.fixture
def app(tmp_path: Path) -> Iterator[TemporaryApp]:
    database = _DATABASE.format(path=(tmp_path / "app.db").as_posix())
    with TemporaryApp(
        tmp_path, bundles=(OrmBundle,), modules={"config.packages.orm": database}
    ) as app:
        yield app


async def test_the_entities_map_migrate_and_store_a_row(app: TemporaryApp) -> None:
    kept = frozenset(orm_registry.metadata.tables)
    for argv in (_AUTHOR, _BOOK):
        code, output = await app.run(argv)
        assert code == ExitCode.SUCCESS, output
    _restart(app, kept)
    author_module = app.import_generated("entity.author")
    author_type = cast("Callable[..., object]", author_module.Author)
    book_module = app.import_generated("entity.book")
    book_type = cast("Callable[..., object]", book_module.Book)
    repository_module = app.import_generated("repository.book_repository")
    repository_type = cast("type[object]", repository_module.BookRepository)

    configure_mappers()
    books, authors = (orm_registry.metadata.tables[name] for name in ("books", "authors"))
    async with await app.boot() as booted:
        engine = await booted.container.get(AsyncEngine)
        async with engine.begin() as connection:
            await connection.run_sync(orm_registry.metadata.create_all)
        async with unit_of_work(booted.container) as unit:
            session = await unit.get(AsyncSession)
            repository = await unit.get(repository_type)
            author = author_type(name="Ursula K. Le Guin")
            session.add(author)
            session.add(book_type(title="The Dispossessed", price=Decimal("9.99"), author=author))
            await session.commit()
            stored = await cast("SQLAlchemyAsyncRepository[UUIDAuditBase]", repository).count()
            joined = await session.scalar(select(func.count()).select_from(books.join(authors)))

    assert stored == 1
    assert joined == 1


async def test_every_field_type_maps_and_creates_its_table(app: TemporaryApp) -> None:
    kept = frozenset(orm_registry.metadata.tables)
    code, output = await app.run(_EVERY_TYPE)
    assert code == ExitCode.SUCCESS, output
    _restart(app, kept)

    _ = app.import_generated("entity.parcel")
    configure_mappers()
    async with await app.boot() as booted:
        engine = await booted.container.get(AsyncEngine)
        async with engine.begin() as connection:
            await connection.run_sync(orm_registry.metadata.create_all)

    assert {"details", "status", "sent_at"} <= set(orm_registry.metadata.tables["parcels"].c.keys())


async def test_the_generated_files_pass_every_lint_rule_and_the_formatter(
    app: TemporaryApp,
) -> None:
    for argv in (
        _AUTHOR,
        _BOOK,
        ["make:entity", "Tag", "--id", "bigint", "--no-audit", "-n"],
        # A key past 88 columns but within 100: split, it must stay split at any width.
        ["make:entity", "Review", "--relation", "reviewing_author:many_to_one:Author?", "-n"],
    ):
        code, output = await app.run(argv)
        assert code == ExitCode.SUCCESS, output
    paths = [str(app.package_dir / path) for path in _GENERATED]

    checked = _ruff(app, "check", "--select", "ALL", "--ignore", _RUFF_IGNORED, *paths)
    formatted = _ruff(app, "format", "--check", *paths)
    wide = _ruff(app, "format", "--check", "--line-length", "100", *paths)

    assert checked.returncode == 0, checked.stdout
    assert formatted.returncode == 0, formatted.stdout
    assert wide.returncode == 0, wide.stdout
    assert "class Tag(BigIntBase):" in app.read("entity/tag.py")


async def test_answers_write_the_entity_without_flags(app: TemporaryApp) -> None:
    code, output = await app.run(["make:entity"], inputs=["Shelf", "label", "", "40", "n", ""])

    assert code == ExitCode.SUCCESS, output
    assert "    label: Mapped[str] = mapped_column(String(40))\n" in app.read("entity/shelf.py")


async def test_the_maker_is_listed_with_the_orm_bundle(app: TemporaryApp) -> None:
    _, listed = await app.run(["list"])

    assert "make:entity" in listed


async def test_the_maker_is_not_offered_without_the_orm_bundle(tmp_path: Path) -> None:
    with TemporaryApp(tmp_path) as bare:
        _, listed = await bare.run(["list"])

    assert "make:entity" not in listed


def _ruff(app: TemporaryApp, *arguments: str) -> subprocess.CompletedProcess[str]:
    """Run the linter as an application would, with its defaults rather than this package's."""
    return subprocess.run(  # noqa: S603 — fixed arguments, the interpreter running the tests.
        [sys.executable, "-m", "ruff", *arguments, "--isolated"],
        cwd=app.project_dir,
        capture_output=True,
        text=True,
        check=False,
    )
