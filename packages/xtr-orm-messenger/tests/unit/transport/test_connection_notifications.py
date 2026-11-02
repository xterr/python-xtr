"""How a connection waits when its database can notify: through a notifier, not its poll interval.

SQLite stands in for PostgreSQL here — the connection is told its dialect is
the one that listens, and the notifier is a fake — so the waiting is checked
without a server. The real thing runs in ``tests/postgresql``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, final

import pytest
from sqlalchemy.dialects.sqlite.aiosqlite import SQLiteDialect_aiosqlite

import xtr_orm_messenger.transport.connection as connection_module
from tests.support.connections import connection_on
from xtr_orm_messenger.transport import OrmOptions

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine
    from xtr_clock import MockClock

pytestmark = pytest.mark.anyio


@final
class FakeNotifier:
    built: ClassVar[list[FakeNotifier]] = []

    def __init__(self, engine: object, channel: str, queue: str) -> None:
        self.channel = channel
        self.queue = queue
        self.listening = False
        self.waits: list[float] = []
        self.closed = False
        FakeNotifier.built.append(self)

    async def listen(self) -> None:
        self.listening = True

    async def wait(self, seconds: float) -> None:
        self.waits.append(seconds)

    async def close(self) -> None:
        self.closed = True


@pytest.fixture
def listening_dialect(monkeypatch: pytest.MonkeyPatch) -> list[FakeNotifier]:
    FakeNotifier.built.clear()
    monkeypatch.setattr(connection_module, "PGDialect_asyncpg", SQLiteDialect_aiosqlite)
    monkeypatch.setattr(connection_module, "PostgreSqlNotifier", FakeNotifier)
    return FakeNotifier.built


async def test_the_first_wait_only_starts_listening(
    engine: AsyncEngine, clock: MockClock, listening_dialect: list[FakeNotifier]
) -> None:
    connection = connection_on(engine, clock, OrmOptions(table_name="jobs", queue="high"))

    await connection.wait()

    (notifier,) = listening_dialect
    assert (notifier.channel, notifier.queue, notifier.listening) == ("jobs", "high", True)
    assert notifier.waits == []
    assert clock.now().isoformat() == "2026-01-01T00:00:00+00:00"


async def test_later_waits_last_the_shorter_of_the_two_intervals(
    engine: AsyncEngine, clock: MockClock, listening_dialect: list[FakeNotifier]
) -> None:
    connection = connection_on(
        engine, clock, OrmOptions(check_delayed_interval=5000, get_notify_timeout=2000)
    )

    await connection.wait()
    await connection.wait()
    await connection.wait()

    (notifier,) = listening_dialect
    assert notifier.waits == [2.0, 2.0]


async def test_closing_stops_the_listening_and_the_next_wait_listens_again(
    engine: AsyncEngine, clock: MockClock, listening_dialect: list[FakeNotifier]
) -> None:
    connection = connection_on(engine, clock)
    await connection.wait()

    await connection.close()
    await connection.wait()

    first, second = listening_dialect
    assert first.closed
    assert second.listening


async def test_without_use_notify_nothing_listens(
    engine: AsyncEngine, clock: MockClock, listening_dialect: list[FakeNotifier]
) -> None:
    connection = connection_on(engine, clock, OrmOptions(use_notify=False, poll_interval=3))

    await connection.wait()

    assert listening_dialect == []
    assert clock.now().isoformat() == "2026-01-01T00:00:03+00:00"
