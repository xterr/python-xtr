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
from typing import TYPE_CHECKING, Final, Never, TypeVar, cast, final

from sqlalchemy import Column, MetaData, String, Table, event, func, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from xtr_orm import ConnectionRegistry

from xtr_security_oauth2_server.model.client import Client
from xtr_security_oauth2_server.persistence.mapping.driver import Driver

from .models import client_model

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Generator
    from pathlib import Path

    from sqlalchemy.engine.interfaces import DBAPIConnection
    from sqlalchemy.ext.asyncio import AsyncEngine
    from sqlalchemy.pool import ConnectionPoolEntry
    from sqlalchemy.types import TypeEngine

    from xtr_security_oauth2_server.model.abstract_client import AbstractClient

__all__ = [
    "CONNECTION",
    "Database",
    "connections_of",
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

_NO_DEFAULT: Final = "a-connection-this-registry-does-not-have"
"""What a registry built here answers for when nothing is named.

Deliberately unregistered: a manager that asked for the default connection
instead of the one it was built for would be refused rather than quietly
reading the right database by accident.
"""


async def _never() -> Never:
    """Stand where a connection's migrator and database manager would be.

    A manager asks a registry for a session and for nothing else, but a
    connection cannot be registered without the other two.
    """
    raise AssertionError("a manager asks a registry only for a session")  # pragma: no cover


def connections_of(session: AsyncSession, connection: str = CONNECTION) -> ConnectionRegistry:
    """Return a registry answering with ``session`` for the connection managers read.

    A stored manager is a singleton and holds no session: it asks the registry
    for the session of the unit of work it is being used in. A test decides
    what that is by handing one over, which is also how it gives two managers
    two different sessions — as two requests have.
    """
    registry = ConnectionRegistry(_NO_DEFAULT)

    async def provide() -> AsyncSession:
        return session

    registry.register(
        connection,
        engine=_never,
        migrator=_never,
        database=_never,
        session=provide,
    )

    return registry


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
    """A SQLite file with one driver's tables on it, and the sessions over it."""

    __slots__ = ("_driver", "_engine", "_metadata", "_sessions", "_statements")

    def __init__(self, engine: AsyncEngine, driver: Driver, metadata: MetaData) -> None:
        self._engine = engine
        self._driver = driver
        self._metadata = metadata
        self._sessions: list[AsyncSession] = []
        self._statements: list[str] = []
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
        """Return a fresh unit of work, as the container hands one out per request."""
        opened = AsyncSession(self._engine)
        self._sessions.append(opened)

        return opened

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
        """Close every session handed out, so none is left for the collector."""
        for opened in self._sessions:
            await opened.close()
        self._sessions.clear()

    def _record(self, *arguments: object) -> None:
        """Remember the statement a cursor is about to run."""
        self._statements.append(cast("str", arguments[2]))


def selects(statements: list[str]) -> list[str]:
    """Return only the reads out of ``statements``."""
    return [statement for statement in statements if statement.lstrip().startswith("SELECT")]


async def registered(session: AsyncSession, identifier: str = "client-1") -> Client:
    """Store a client through ``session``, and hand back the instance it knows.

    A credential is written through the client it holds, so that client has to
    be one the session already knows — which is what a stored deployment hands
    its managers: one session for the whole request, the client read through it.
    """
    client = client_model(identifier)
    session.add(client)
    await session.commit()

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
