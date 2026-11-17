"""A SQLite file carrying the tables a driver builds, and sessions over them.

The stored managers are tested against a real database — a file in the test's
own directory — because what is being checked *is* the SQL: the row count a
conditional update reports, a sweep that has to unlink before it deletes, the
one statement a read of a credential costs, a client deletion that takes the
codes with it. None of that shows against a double.

SQLite only honours a foreign key when the connection asks it to, so every
connection opened here turns the enforcement on; without that the cascade
tests would pass against a database that silently keeps orphans.
"""

from __future__ import annotations

from contextlib import asynccontextmanager, contextmanager
from typing import TYPE_CHECKING, Final, TypeVar, cast, final

from sqlalchemy import Column, MetaData, String, Table, event, func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from xtr_dependency_injection import Kernel, ScopeFactoryInterface
from xtr_orm.bundle import OrmBundle

from xtr_security_oauth2_server.model.client import Client
from xtr_security_oauth2_server.persistence.mapping.driver import Driver

from .models import client_model

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Generator
    from pathlib import Path

    from sqlalchemy.engine.interfaces import DBAPIConnection
    from sqlalchemy.pool import ConnectionPoolEntry
    from sqlalchemy.types import TypeEngine
    from xtr_dependency_injection.kernel.booted_kernel import BootedKernel

    from xtr_security_oauth2_server.model.abstract_client import AbstractClient

__all__ = [
    "CONNECTION",
    "Database",
    "enforce_foreign_keys",
    "orm_driver",
    "registered",
    "round_trip",
    "selects",
    "stored",
]

_ValueT = TypeVar("_ValueT")

CONNECTION: Final = "default"
"""The connection every stored manager in these tests reads and writes through."""


def orm_driver(
    *,
    client_class: type[AbstractClient] = Client,
    persist_access_token: bool = True,
    table_prefix: str = "oauth2_",
    enable_device_code_grant: bool = True,
) -> Driver:
    """Return a driver with everything mapped, which is what most tests want."""
    return Driver(client_class, persist_access_token, table_prefix, enable_device_code_grant)


@final
class Database:
    """A SQLite file with one driver's tables on it, the sessions over it, and its units of work.

    The stored managers open a unit of work of their own for each read and
    write, through a kernel's scope factory: :meth:`scope_factory` boots one
    holding nothing but the orm bundle, on this very file, so every unit they
    open is a real one.
    """

    __slots__ = ("_booted", "_driver", "_engine", "_metadata", "_sessions", "_statements")

    def __init__(self, engine: AsyncEngine, driver: Driver, metadata: MetaData) -> None:
        self._engine = engine
        self._driver = driver
        self._metadata = metadata
        self._sessions: list[AsyncSession] = []
        self._statements: list[str] = []
        self._booted: BootedKernel | None = None
        event.listen(engine.sync_engine, "before_cursor_execute", self._record)

    @property
    def driver(self) -> Driver:
        """The driver whose tables this database carries."""
        return self._driver

    @property
    def metadata(self) -> MetaData:
        """The definitions the driver's tables were loaded into."""
        return self._metadata

    def table(self, name: str) -> Table:
        """Return the table loaded under ``name``."""
        return self._metadata.tables[name]

    def session(self) -> AsyncSession:
        """Return a fresh session, built as the orm bundle builds a unit's: kept on commit."""
        opened = AsyncSession(self._engine, expire_on_commit=False)
        self._sessions.append(opened)

        return opened

    async def scope_factory(self) -> ScopeFactoryInterface:
        """Return the scope factory of a kernel serving this file, booted the first time asked."""
        if self._booted is None:
            kernel = Kernel(
                "tests.fixtures.orm_units_app",
                env="test",
                bundles={OrmBundle: {"all": True}},
                environ={"DATABASE_URL": self._engine.url.render_as_string(hide_password=False)},
            )
            self._booted = await kernel.boot()
            served = await self._booted.container.get(AsyncEngine)
            enforce_foreign_keys(served)
            event.listen(served.sync_engine, "before_cursor_execute", self._record)

        return await self._booted.container.get(ScopeFactoryInterface)

    async def count(self, name: str) -> int:
        """Return how many rows the table ``name`` holds, read in a session of its own."""
        async with self.session() as session:
            counted = await session.execute(select(func.count()).select_from(self.table(name)))

            return counted.scalar_one()

    @contextmanager
    def watching(self) -> Generator[list[str], None, None]:
        """Collect the statements the database runs while the block is open."""
        self._statements.clear()
        try:
            yield self._statements
        finally:
            self._statements.clear()

    async def close(self) -> None:
        """Close every session handed out, and shut the kernel down, so nothing is left behind."""
        for opened in self._sessions:
            await opened.close()
        self._sessions.clear()
        if self._booted is not None:
            await self._booted.shutdown()
            self._booted = None

    def _record(self, *arguments: object) -> None:
        """Remember the statement a cursor is about to run."""
        self._statements.append(cast("str", arguments[2]))


def selects(statements: list[str]) -> list[str]:
    """Return only the reads out of ``statements``."""
    return [statement for statement in statements if statement.lstrip().startswith("SELECT")]


async def registered(session: AsyncSession, identifier: str = "client-1") -> Client:
    """Store a client through ``session``, and hand it back detached.

    A stored manager reads a client in a unit of work of its own and hands it
    back detached once that unit ends, so that is what a credential is written
    with: a client no open session holds.
    """
    client = client_model(identifier)
    session.add(client)
    await session.commit()
    session.expunge(client)

    return client


def enforce_foreign_keys(engine: AsyncEngine) -> None:
    """Make every connection of ``engine`` honour the foreign keys it is given."""

    @event.listens_for(engine.sync_engine, "connect")
    def _pragma(connection: DBAPIConnection, _record: ConnectionPoolEntry) -> None:
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


@asynccontextmanager
async def stored(
    tmp_path: Path,
    driver: Driver | None = None,
    metadata: MetaData | None = None,
) -> AsyncGenerator[Database, None]:
    """Create ``driver``'s tables in a SQLite file under ``tmp_path``, then clean up.

    The driver's registry is disposed on the way out: the mapping it installs
    is on the model classes, which the whole process shares, so a test leaving
    it behind would decide what the next test is mapped against.
    """
    built = driver if driver is not None else orm_driver()
    definitions = metadata if metadata is not None else MetaData()
    _ = built.load_metadata(definitions)
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'oauth2.sqlite'}")
    enforce_foreign_keys(engine)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(definitions.create_all)
        database = Database(engine, built, definitions)
        try:
            yield database
        finally:
            await database.close()
    finally:
        await engine.dispose()
        built._dispose()


async def round_trip(
    tmp_path: Path,
    column_type: TypeEngine[_ValueT],
    value: _ValueT | None,
) -> _ValueT | None:
    """Store ``value`` in a one-column table of ``column_type``, and read it back.

    A column type is only worth anything through a database: what a decorator
    hands the driver and what the driver hands back are two conversions, and a
    test calling them one at a time would miss the pair not meeting.
    """
    metadata = MetaData()
    table = Table(
        "round_trip",
        metadata,
        Column("identifier", String(8), primary_key=True),
        Column("value", column_type, nullable=True),
    )
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'round-trip.sqlite'}")
    try:
        async with engine.begin() as connection:
            await connection.run_sync(metadata.create_all)
        async with AsyncSession(engine) as session:
            _ = await session.execute(table.insert().values(identifier="one", value=value))
            await session.commit()
            read = await session.execute(select(table.c["value"]))

            return cast("_ValueT | None", read.scalar_one())
    finally:
        await engine.dispose()
