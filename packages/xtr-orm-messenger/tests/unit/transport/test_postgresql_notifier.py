from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, cast, final

import pytest

from xtr_orm_messenger.transport import PostgreSqlNotifier

if TYPE_CHECKING:
    from collections.abc import Callable

    from sqlalchemy.ext.asyncio import AsyncEngine

pytestmark = pytest.mark.anyio


@final
class FakeDriver:
    """The listening part of the PostgreSQL driver's connection."""

    def __init__(self, *, fails: bool = False) -> None:
        self.listeners: dict[str, list[Callable[[object, int, str, str], None]]] = {}
        self.fails = fails

    async def add_listener(
        self, channel: str, callback: Callable[[object, int, str, str], None]
    ) -> None:
        if self.fails:
            raise ConnectionError("LISTEN refused")
        self.listeners.setdefault(channel, []).append(callback)

    async def remove_listener(
        self, channel: str, callback: Callable[[object, int, str, str], None]
    ) -> None:
        self.listeners[channel].remove(callback)

    def notify(self, channel: str, payload: str) -> None:
        for callback in self.listeners.get(channel, []):
            callback(self, 1, channel, payload)


@final
class FakeRaw:
    def __init__(self, driver: FakeDriver) -> None:
        self.driver_connection = driver


@final
class FakeConnection:
    def __init__(self, driver: FakeDriver) -> None:
        self._driver = driver
        self.closed = False

    async def get_raw_connection(self) -> FakeRaw:
        return FakeRaw(self._driver)

    async def close(self) -> None:
        self.closed = True


@final
class FakeEngine:
    def __init__(self, driver: FakeDriver) -> None:
        self.driver = driver
        self.connections: list[FakeConnection] = []

    async def connect(self) -> FakeConnection:
        connection = FakeConnection(self.driver)
        self.connections.append(connection)
        return connection


def _notifier(engine: FakeEngine, queue: str = "default") -> PostgreSqlNotifier:
    return PostgreSqlNotifier(
        cast("AsyncEngine", cast("object", engine)), "messenger_messages", queue
    )


async def test_building_one_opens_nothing() -> None:
    engine = FakeEngine(FakeDriver())

    _ = _notifier(engine)

    assert engine.connections == []


async def test_a_notification_naming_the_queue_ends_the_wait() -> None:
    engine = FakeEngine(FakeDriver())
    notifier = _notifier(engine)
    await notifier.listen()

    waiting = asyncio.ensure_future(notifier.wait(30))
    await asyncio.sleep(0)
    engine.driver.notify("messenger_messages", "default")

    await asyncio.wait_for(waiting, 1)


async def test_a_notification_for_another_queue_is_ignored() -> None:
    engine = FakeEngine(FakeDriver())
    notifier = _notifier(engine)
    await notifier.listen()
    engine.driver.notify("messenger_messages", "reports")

    await notifier.wait(0.01)


async def test_a_notification_heard_while_nobody_waited_ends_the_next_wait_at_once() -> None:
    engine = FakeEngine(FakeDriver())
    notifier = _notifier(engine)
    await notifier.listen()
    engine.driver.notify("messenger_messages", "default")

    await asyncio.wait_for(notifier.wait(30), 1)
    await notifier.wait(0.01)


async def test_listening_twice_takes_one_connection() -> None:
    engine = FakeEngine(FakeDriver())
    notifier = _notifier(engine)

    await notifier.listen()
    await notifier.listen()

    assert len(engine.connections) == 1
    assert len(engine.driver.listeners["messenger_messages"]) == 1


async def test_a_listen_that_fails_gives_its_connection_back() -> None:
    engine = FakeEngine(FakeDriver(fails=True))
    notifier = _notifier(engine)

    with pytest.raises(ConnectionError):
        await notifier.listen()

    assert engine.connections[0].closed


async def test_closing_stops_listening_and_gives_the_connection_back() -> None:
    engine = FakeEngine(FakeDriver())
    notifier = _notifier(engine)
    await notifier.listen()

    await notifier.close()
    await notifier.close()

    assert engine.driver.listeners["messenger_messages"] == []
    assert engine.connections[0].closed
