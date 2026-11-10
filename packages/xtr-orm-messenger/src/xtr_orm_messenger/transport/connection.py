"""The statements an ``orm://`` transport runs against its table.

Everything that touches the database is here, so the receiver and the sender
deal in rows and never in SQL. A worker claims the oldest message of its queue
that is due and not handed out, marking it handed out in the same transaction;
a message handed out and never settled is handed out again once
``redeliver_timeout`` has passed, the worker holding it being taken for dead.
Settling a message — handled or rejected — deletes it.

A claim selects the oldest due row ``FOR UPDATE SKIP LOCKED`` and marks it
handed out, in one transaction, so concurrent workers each take a different row
without waiting on each other. A database without row locks — SQLite — gets the
same statements with the lock clause left out; its single writer then turns two
workers reaching for one row into a "database is locked" error for the second,
which the receiver treats as a conflict worth trying again.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Final, TypeVar, cast, final

import msgspec
from sqlalchemy import (
    CursorResult,
    MetaData,
    and_,
    delete,
    func,
    insert,
    literal,
    or_,
    select,
    update,
)
from sqlalchemy.dialects.postgresql.asyncpg import PGDialect_asyncpg
from sqlalchemy.dialects.postgresql.base import PGDialect
from sqlalchemy.exc import DBAPIError
from xtr_clock import SystemClock
from xtr_orm.exception import SessionUnavailableError

from ._database_errors import is_missing_table
from .messages_table import messages_table
from .postgresql_notifier import PostgreSqlNotifier
from .stored_message import StoredMessage

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable, Mapping, Sequence

    from sqlalchemy import ColumnElement, Executable, RowMapping, Select, Table
    from sqlalchemy import Connection as SyncConnection
    from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
    from xtr_clock import ClockInterface

    from .orm_options import OrmOptions

__all__ = ["LISTING_PAGE_SIZE", "Connection"]

_T = TypeVar("_T")

LISTING_PAGE_SIZE: Final = 100
"""How many rows :meth:`Connection.all` reads per statement when it lists every message."""


@final
class Connection:
    """Sends, claims, settles and lists the messages of one queue of one table.

    Built with what reaches the engine rather than the engine itself, so that
    building one does no I/O and reads no configuration: the engine is asked
    for the first time a statement runs.
    """

    __slots__ = (
        "_auto_setup",
        "_clock",
        "_engine_factory",
        "_notifier",
        "_notifier_resolved",
        "_options",
        "_session_factory",
        "_table",
    )

    def __init__(
        self,
        engine_factory: Callable[[], Awaitable[AsyncEngine]],
        options: OrmOptions,
        *,
        session_factory: Callable[[], Awaitable[AsyncSession]] | None = None,
        clock: ClockInterface | None = None,
    ) -> None:
        """Run statements on the engine ``engine_factory`` returns, as ``options`` say.

        Args:
            engine_factory: Returns the engine of the connection the table is
                on; called each time a statement runs, so it must hand back the
                same engine every time.
            options: The table, the queue and how to treat them.
            session_factory: Returns the session of the unit of work under
                way, raising
                :class:`~xtr_orm.exception.SessionUnavailableError` outside of
                one; consulted to send when ``options.transactional`` is on.
            clock: What reads the time; the system clock when left out.
        """
        self._engine_factory = engine_factory
        self._options = options
        self._session_factory = session_factory
        self._clock: ClockInterface = clock if clock is not None else SystemClock()
        self._table: Table = messages_table(MetaData(), options.table_name)
        self._auto_setup = options.auto_setup
        self._notifier: PostgreSqlNotifier | None = None
        self._notifier_resolved = False

    @property
    def options(self) -> OrmOptions:
        """The table, the queue and how this connection treats them."""
        return self._options

    @property
    def table(self) -> Table:
        """The messages table, as this connection defines it."""
        return self._table

    async def send(self, body: str, headers: Mapping[str, str], delay_ms: int = 0) -> str:
        """Keep a message, due ``delay_ms`` milliseconds from now; return its id.

        A positive delay is rounded up to a whole second: some databases keep
        a datetime to the second, and dropping the fraction would make the
        message due before the delay asked for.

        With ``transactional`` on and a unit of work under way, the message is
        written in that unit's session and is sent only once the unit commits.
        """
        now = self._now()
        available_at = now + timedelta(milliseconds=delay_ms)
        if delay_ms > 0 and available_at.microsecond:
            available_at = available_at.replace(microsecond=0) + timedelta(seconds=1)
        statement = insert(self._table).values(
            body=body,
            headers=msgspec.json.encode(dict(headers)).decode(),
            queue_name=self._options.queue,
            created_at=now,
            available_at=available_at,
        )
        session = await self._unit_session()
        if session is not None:
            return await self._send_in(session, statement)
        return await self._with_setup(lambda: self._send_alone(statement))

    async def get(self) -> StoredMessage | None:
        """Claim the oldest message of the queue that is due, or return ``None``.

        The message is marked handed out in the same transaction, so no other
        worker claims it until :meth:`ack`, :meth:`reject` or
        ``redeliver_timeout`` releases it.
        """
        return await self._with_setup(self._claim)

    async def ack(self, message_id: str) -> None:
        """Forget the message ``message_id``: it was handled."""
        await self._with_setup(lambda: self._delete(message_id))

    async def reject(self, message_id: str) -> None:
        """Forget the message ``message_id``: it failed for good.

        The same as :meth:`ack`: whatever retries a message gets have run by
        the time it is rejected, and keeping it would hand it out again.
        """
        await self._with_setup(lambda: self._delete(message_id))

    async def keepalive(self, message_id: str) -> None:
        """Mark the message ``message_id`` handed out now, restarting its redelivery clock.

        For a handler that runs longer than ``redeliver_timeout``: called
        while it runs, the message is not handed to another worker under it.
        """
        now = self._now()
        statement = (
            update(self._table).where(self._table.c.id == int(message_id)).values(delivered_at=now)
        )
        await self._with_setup(lambda: self._execute(statement))

    async def find(self, message_id: str) -> StoredMessage | None:
        """Return the message ``message_id`` of the queue, handed out or not, if it is kept."""
        table = self._table
        statement = select(table).where(
            table.c.id == int(message_id), table.c.queue_name == self._options.queue
        )
        return await self._with_setup(lambda: self._first(statement))

    async def all(self, limit: int | None = None) -> AsyncIterator[StoredMessage]:
        """Yield the messages of the queue a worker could claim now, oldest first.

        With no ``limit``, every one is listed, read :data:`LISTING_PAGE_SIZE`
        at a time so a long queue is never held in memory whole.
        """
        table = self._table
        now = self._now()
        remaining = limit
        after: StoredMessage | None = None
        while remaining is None or remaining > 0:
            size = LISTING_PAGE_SIZE if remaining is None else min(remaining, LISTING_PAGE_SIZE)
            condition = self._available(now)
            if after is not None:
                condition = and_(
                    condition,
                    or_(
                        table.c.available_at > after.available_at,
                        and_(
                            table.c.available_at == after.available_at,
                            table.c.id > int(after.id),
                        ),
                    ),
                )
            statement = (
                select(table)
                .where(condition)
                .order_by(table.c.available_at, table.c.id)
                .limit(size)
            )
            page = await self._with_setup(lambda statement=statement: self._rows(statement))
            for message in page:
                yield message
            if len(page) < size:
                return
            after = page[-1]
            if remaining is not None:
                remaining -= len(page)

    async def count(self) -> int:
        """Return how many messages of the queue a worker could claim now."""
        statement = (
            select(func.count()).select_from(self._table).where(self._available(self._now()))
        )
        return await self._with_setup(lambda: self._scalar(statement))

    async def setup(self) -> None:
        """Create the messages table if it does not exist; an existing one is left as it is."""
        engine = await self._engine_factory()
        async with engine.begin() as connection:
            await connection.run_sync(self._create_table)
        self._auto_setup = False

    async def ping(self) -> bool:
        """Tell whether the database answers, opening a connection if the pool holds none."""
        try:
            await self._execute(select(literal(1)))
        except DBAPIError:
            return False
        return True

    async def wait(self) -> None:
        """Wait before a worker asks again, having found nothing due.

        On PostgreSQL through asyncpg with ``use_notify``, until a message is
        sent to the queue or ``check_delayed_interval`` passes, whichever is
        first; anywhere else, ``poll_interval``.

        The first time a PostgreSQL worker waits it only starts listening and
        returns: a message sent between the poll that found nothing and the
        moment the listening started announced itself to nobody, so the worker
        asks once more before it waits for real.
        """
        if not self._notifier_resolved:
            await self._resolve_notifier()
            if self._notifier is not None:
                return
        notifier = self._notifier
        if notifier is None:
            await self._clock.sleep_async(self._options.poll_interval)
            return
        options = self._options
        await notifier.wait(min(options.check_delayed_interval, options.get_notify_timeout) / 1000)

    async def close(self) -> None:
        """Release the connection a PostgreSQL worker listens for notifications on."""
        notifier = self._notifier
        self._notifier = None
        self._notifier_resolved = False
        if notifier is not None:
            await notifier.close()

    async def _with_setup(self, operation: Callable[[], Awaitable[_T]]) -> _T:
        """Run ``operation``; on a missing table, with ``auto_setup``, create it and run again."""
        try:
            return await operation()
        except DBAPIError as error:
            if not self._auto_setup or not is_missing_table(error):
                raise
        await self.setup()
        return await operation()

    async def _unit_session(self) -> AsyncSession | None:
        """Return the session to send in, or ``None`` to send in a transaction of its own."""
        if not self._options.transactional or self._session_factory is None:
            return None
        try:
            return await self._session_factory()
        except SessionUnavailableError:
            return None

    async def _send_in(self, session: AsyncSession, statement: Executable) -> str:
        """Write the message in ``session``, which its unit of work commits or rolls back.

        The table is set up first when ``auto_setup`` is on, in a transaction of
        its own: a failed statement inside the unit's transaction would abort
        the handler's own changes along with it on some databases.
        """
        if self._auto_setup:
            await self.setup()
        result = cast("CursorResult[tuple[object, ...]]", await session.execute(statement))
        if isinstance(session.get_bind().dialect, PGDialect):
            _ = await session.execute(self._notification())
        return _identifier(result)

    async def _send_alone(self, statement: Executable) -> str:
        engine = await self._engine_factory()
        async with engine.begin() as connection:
            result = await connection.execute(statement)
            if isinstance(connection.dialect, PGDialect):
                _ = await connection.execute(self._notification())
        return _identifier(result)

    def _notification(self) -> Executable:
        """Announce a message on the table's channel, naming its queue.

        Sent in the transaction that wrote the message, so a listener hears it
        only once the message can be claimed.
        """
        return select(func.pg_notify(self._options.table_name, self._options.queue))

    async def _claim(self) -> StoredMessage | None:
        now = self._now()
        table = self._table
        statement = (
            select(table)
            .where(self._available(now))
            .order_by(table.c.available_at, table.c.id)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        engine = await self._engine_factory()
        async with engine.begin() as connection:
            row = (await connection.execute(statement)).mappings().first()
            if row is None:
                return None
            stored = _stored(row)
            _ = await connection.execute(
                update(table).where(table.c.id == int(stored.id)).values(delivered_at=now)
            )
        return replace(stored, delivered_at=now)

    def _available(self, now: datetime) -> ColumnElement[bool]:
        """Select the queue's messages that are due and not held by a worker that is still alive."""
        table = self._table
        handed_out_before = now - timedelta(seconds=self._options.redeliver_timeout)
        return and_(
            table.c.queue_name == self._options.queue,
            or_(table.c.delivered_at.is_(None), table.c.delivered_at < handed_out_before),
            table.c.available_at <= now,
        )

    async def _delete(self, message_id: str) -> None:
        await self._execute(delete(self._table).where(self._table.c.id == int(message_id)))

    async def _execute(self, statement: Executable) -> None:
        engine = await self._engine_factory()
        async with engine.begin() as connection:
            _ = await connection.execute(statement)

    async def _first(self, statement: Executable) -> StoredMessage | None:
        engine = await self._engine_factory()
        async with engine.connect() as connection:
            row = (await connection.execute(statement)).mappings().first()
        return None if row is None else _stored(row)

    async def _rows(self, statement: Executable) -> list[StoredMessage]:
        engine = await self._engine_factory()
        async with engine.connect() as connection:
            rows = (await connection.execute(statement)).mappings().all()
        return [_stored(row) for row in rows]

    async def _scalar(self, statement: Select[int]) -> int:
        engine = await self._engine_factory()
        async with engine.connect() as connection:
            return (await connection.execute(statement)).scalar_one()

    def _create_table(self, connection: SyncConnection) -> None:
        self._table.metadata.create_all(connection, tables=[self._table], checkfirst=True)

    async def _resolve_notifier(self) -> None:
        """Start listening when this connection waits through notifications.

        That is PostgreSQL through asyncpg with ``use_notify``: the listening
        goes through asyncpg's own connection, so another PostgreSQL driver
        polls instead.
        """
        self._notifier_resolved = True
        if not self._options.use_notify:
            return
        engine = await self._engine_factory()
        if not isinstance(engine.dialect, PGDialect_asyncpg):
            return
        notifier = PostgreSqlNotifier(engine, self._options.table_name, self._options.queue)
        await notifier.listen()
        self._notifier = notifier

    def _now(self) -> datetime:
        """Return the current instant as the naive UTC datetime the table keeps."""
        return self._clock.now().to_naive_utc()


def _identifier(result: CursorResult[tuple[object, ...]]) -> str:
    """Return the id the database gave the row ``result`` inserted."""
    key = result.inserted_primary_key
    if key is None:  # pragma: no cover — every supported database reports the key of an insert
        message = "the database reported no key for the inserted message"
        raise RuntimeError(message)
    values = cast("Sequence[object]", key)
    return str(values[0])


def _stored(row: RowMapping) -> StoredMessage:
    """Read one row of the table into a :class:`StoredMessage`."""
    # The table's columns are untyped to SQLAlchemy; their types are the table's own.
    values = cast("Mapping[str, object]", row)
    return StoredMessage(
        id=str(values["id"]),
        body=cast("str", values["body"]),
        headers=msgspec.json.decode(cast("str", values["headers"]), type=dict[str, str]),
        queue=cast("str", values["queue_name"]),
        created_at=cast("datetime", values["created_at"]),
        available_at=cast("datetime", values["available_at"]),
        delivered_at=cast("datetime | None", values["delivered_at"]),
    )
