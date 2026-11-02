"""Waking a waiting worker the moment a message is sent, through PostgreSQL notifications.

Every message an ``orm://`` transport writes on PostgreSQL is announced on the
table's channel, its queue as the payload, in the transaction that wrote it. A
worker that found nothing due listens on that channel instead of sleeping
through its poll interval, and asks again as soon as its own queue is named.

Listening takes a connection of its own for as long as the worker runs: a
notification is delivered to the session that asked for it, so the connection
cannot go back to the pool between waits.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Protocol, cast, final

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

__all__ = ["PostgreSqlNotifier"]


class _Listening(Protocol):
    """The part of the PostgreSQL driver's connection notifications go through."""

    def add_listener(
        self, channel: str, callback: Callable[[object, int, str, str], None]
    ) -> Awaitable[None]: ...

    def remove_listener(
        self, channel: str, callback: Callable[[object, int, str, str], None]
    ) -> Awaitable[None]: ...


@final
class PostgreSqlNotifier:
    """Listens on a table's channel and wakes a waiting worker when its queue is named."""

    __slots__ = ("_channel", "_connection", "_driver", "_engine", "_queue", "_woken")

    def __init__(self, engine: AsyncEngine, channel: str, queue: str) -> None:
        """Listen on ``channel`` through ``engine``, waking for ``queue``'s messages only.

        Building one opens nothing; :meth:`listen` does.
        """
        self._engine = engine
        self._channel = channel
        self._queue = queue
        self._woken = asyncio.Event()
        self._connection: AsyncConnection | None = None
        self._driver: _Listening | None = None

    async def listen(self) -> None:
        """Take a connection of the engine's and start listening on it.

        A notification sent from here on is heard; one sent before is not,
        which is why a worker asks for its messages once more before it first
        waits.
        """
        if self._driver is not None:
            return
        connection = await self._engine.connect()
        try:
            raw = await connection.get_raw_connection()
            driver = cast("_Listening", raw.driver_connection)
            await driver.add_listener(self._channel, self._heard)
        except BaseException:
            await connection.close()
            raise
        self._connection = connection
        self._driver = driver

    async def wait(self, seconds: float) -> None:
        """Return once the queue is named on the channel, or ``seconds`` pass.

        A notification heard while nobody waited is kept, so the next wait
        returns at once: the message it announced may still be unclaimed.
        """
        try:
            async with asyncio.timeout(seconds):
                _ = await self._woken.wait()
        except TimeoutError:
            return
        self._woken.clear()

    async def close(self) -> None:
        """Stop listening and give the connection back."""
        driver, connection = self._driver, self._connection
        self._driver = None
        self._connection = None
        if driver is None or connection is None:
            return
        try:
            await driver.remove_listener(self._channel, self._heard)
        finally:
            await connection.close()

    def _heard(self, connection: object, pid: int, channel: str, payload: str) -> None:
        """Wake the waiting worker when the notification names its queue."""
        del connection, pid, channel
        if payload == self._queue:
            self._woken.set()
