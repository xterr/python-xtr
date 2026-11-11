"""Run control on a database table."""

from __future__ import annotations

from datetime import UTC, datetime
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Final, cast, final

import pydantic
from pydantic_ai.usage import RunUsage
from sqlalchemy import MetaData, insert, select, update
from sqlalchemy.exc import IntegrityError
from typing_extensions import override
from xtr_ai import AbstractRunControl, RunState, RunStatus
from xtr_ai.abstract_run_control import (
    DEFAULT_CANCEL_POLL_INTERVAL,
    DEFAULT_HEARTBEAT_INTERVAL,
    DEFAULT_STALE_AFTER,
)

from .run_table import DEFAULT_TABLE_PREFIX, run_table

if TYPE_CHECKING:
    from datetime import timedelta

    from sqlalchemy import Row
    from sqlalchemy.ext.asyncio import AsyncEngine
    from xtr_clock import ClockInterface

__all__ = ["OrmRunControl"]

_USAGE: Final = pydantic.TypeAdapter(RunUsage)
_METADATA: Final = pydantic.TypeAdapter(dict[str, Any])
_INSERT_ATTEMPTS: Final = 2
"""Inserts refused while the conversation's holder was ending, before a last one that raises."""


@final
class OrmRunControl(AbstractRunControl):
    """Runs in ``{prefix}run``, shared by every process on the same database.

    Every call runs in a short transaction of its own on ``engine`` — give it
    the primary's — and commits before it returns, so a cancellation one
    process asks for is what the watching process reads next, and a run's end
    is recorded even when the caller's own work rolls back. One top-level run
    per conversation is held by a unique index; a run whose process stopped
    reporting is taken over as :class:`~xtr_ai.AbstractRunControl` describes.

    ```python
    run_control = OrmRunControl(engine)
    ```
    """

    def __init__(  # noqa: PLR0913 — the engine, the table, and the shared clock and timings
        self,
        engine: AsyncEngine,
        *,
        table_prefix: str = DEFAULT_TABLE_PREFIX,
        clock: ClockInterface | None = None,
        cancel_poll_interval: float = DEFAULT_CANCEL_POLL_INTERVAL,
        heartbeat_interval: timedelta = DEFAULT_HEARTBEAT_INTERVAL,
        stale_after: timedelta = DEFAULT_STALE_AFTER,
    ) -> None:
        """Keep runs through ``engine``, in a table whose name starts with ``table_prefix``."""
        super().__init__(
            clock=clock,
            cancel_poll_interval=cancel_poll_interval,
            heartbeat_interval=heartbeat_interval,
            stale_after=stale_after,
        )
        self._engine = engine
        self._table = run_table(MetaData(), table_prefix)

    @override
    async def _insert(self, status: RunStatus) -> RunStatus | None:
        active_key = status.conversation_id if status.holds_conversation else None
        row = {
            "run_id": status.run_id,
            "agent": status.agent,
            "conversation_id": status.conversation_id,
            "parent_run_id": status.parent_run_id,
            "state": int(status.state),
            "cancel_requested": status.cancel_requested,
            "usage": None,
            "metadata": _METADATA.dump_json(dict(status.metadata)).decode(),
            "started_at": _naive_utc(status.started_at),
            "heartbeat_at": _naive_utc(status.heartbeat_at),
            "finished_at": None,
            "active_key": active_key,
        }
        for _attempt in range(_INSERT_ATTEMPTS):
            try:
                async with self._engine.begin() as connection:
                    _ = await connection.execute(insert(self._table).values(row))
            except IntegrityError:
                holder = await self._holder(active_key) if active_key is not None else None
                if holder is not None:
                    return holder
                # No holder: it ended between the refusal and the read — try again — or the
                # refusal is the run id itself, used twice, which the last attempt re-raises.
                continue
            return None
        async with self._engine.begin() as connection:
            _ = await connection.execute(insert(self._table).values(row))
        return None

    @override
    async def _read(self, run_id: str) -> RunStatus | None:
        table = self._table
        async with self._engine.connect() as connection:
            row = (await connection.execute(select(table).where(table.c.run_id == run_id))).first()
        return _status(row) if row is not None else None

    @override
    async def _poll(self, run_id: str, heartbeat_at: datetime | None) -> bool:
        table = self._table
        if heartbeat_at is not None:
            async with self._engine.begin() as connection:
                _ = await connection.execute(
                    update(table)
                    .where(table.c.run_id == run_id, table.c.state == int(RunState.RUNNING))
                    .values(heartbeat_at=_naive_utc(heartbeat_at))
                )
        # Read outside a transaction: a poll every second must not hold a lock that keeps a
        # writer waiting, which on SQLite would starve every other connection's commits.
        async with self._engine.connect() as connection:
            row = (
                await connection.execute(
                    select(table.c.cancel_requested, table.c.state).where(table.c.run_id == run_id)
                )
            ).first()
        # Gone, flagged, or ended by another process taking it for dead: stop either way.
        return row is None or bool(row.cancel_requested) or row.state != int(RunState.RUNNING)

    @override
    async def _flag_cancel(self, run_id: str) -> bool:
        table = self._table
        async with self._engine.begin() as connection:
            result = await connection.execute(
                update(table)
                .where(table.c.run_id == run_id, table.c.state == int(RunState.RUNNING))
                .values(cancel_requested=True)
            )
        return result.rowcount == 1

    @override
    async def _finish(
        self,
        run_id: str,
        state: RunState,
        usage: RunUsage | None,
        finished_at: datetime,
    ) -> bool:
        table = self._table
        async with self._engine.begin() as connection:
            result = await connection.execute(
                update(table)
                .where(table.c.run_id == run_id, table.c.state == int(RunState.RUNNING))
                .values(
                    state=int(state),
                    usage=_USAGE.dump_json(usage).decode() if usage is not None else None,
                    finished_at=_naive_utc(finished_at),
                    active_key=None,
                )
            )
        return result.rowcount == 1

    async def _holder(self, conversation_id: str) -> RunStatus | None:
        table = self._table
        async with self._engine.connect() as connection:
            row = (
                await connection.execute(select(table).where(table.c.active_key == conversation_id))
            ).first()
        return _status(row) if row is not None else None


def _status(row: Row[Any]) -> RunStatus:
    usage = cast("str | None", row.usage)
    finished_at = cast("datetime | None", row.finished_at)
    return RunStatus(
        run_id=cast("str", row.run_id),
        agent=cast("str", row.agent),
        state=RunState(cast("int", row.state)),
        conversation_id=cast("str | None", row.conversation_id),
        parent_run_id=cast("str | None", row.parent_run_id),
        cancel_requested=bool(row.cancel_requested),
        usage=_USAGE.validate_json(usage) if usage is not None else None,
        metadata=MappingProxyType(_METADATA.validate_json(cast("str", row.metadata))),
        started_at=cast("datetime", row.started_at).replace(tzinfo=UTC),
        heartbeat_at=cast("datetime", row.heartbeat_at).replace(tzinfo=UTC),
        finished_at=finished_at.replace(tzinfo=UTC) if finished_at is not None else None,
    )


def _naive_utc(instant: datetime) -> datetime:
    """``instant``'s UTC wall clock without a zone, as a zone-less column keeps it everywhere."""
    utc = instant.astimezone(UTC)
    return datetime(  # noqa: DTZ001 — a zone-less column wants exactly a naive value
        utc.year, utc.month, utc.day, utc.hour, utc.minute, utc.second, utc.microsecond
    )
