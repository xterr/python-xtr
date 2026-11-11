"""The behaviour every run-control backend shares, over five storage primitives."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Final

import anyio
from pydantic_ai.exceptions import RunCancelled
from typing_extensions import override
from xtr_clock import SystemClock

from xtr_ai.exception import InvalidConfigurationError, RunInProgressError, UnknownRunError
from xtr_ai.run_control_interface import RunControlInterface
from xtr_ai.run_state import RunState
from xtr_ai.run_status import RunStatus
from xtr_ai.watched_run import WatchedRun

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Mapping

    from pydantic_ai import CancellationToken
    from pydantic_ai.usage import RunUsage
    from xtr_clock import ClockInterface

__all__ = [
    "DEFAULT_CANCEL_POLL_INTERVAL",
    "DEFAULT_HEARTBEAT_INTERVAL",
    "DEFAULT_STALE_AFTER",
    "AbstractRunControl",
]

DEFAULT_CANCEL_POLL_INTERVAL: Final = 1.0
"""Seconds between two reads of a watched run's cancel flag."""

DEFAULT_HEARTBEAT_INTERVAL: Final = timedelta(seconds=10)
"""How often a watched run reports itself alive."""

DEFAULT_STALE_AFTER: Final = timedelta(seconds=60)
"""How long a running run may go without reporting before another may take its conversation."""


class AbstractRunControl(RunControlInterface, ABC):
    """Run control over a backend that implements five storage primitives.

    The backend stores and reads runs; this class decides what they mean:
    which run holds a conversation, when a silent run is taken to have died,
    what state a watched block ends in, and that the first terminal state
    written wins. A backend for another store subclasses it and implements the
    primitives; :class:`~xtr_ai.testing.run_control_contract.RunControlContract`
    checks it.

    A watched run reports itself alive every ``heartbeat_interval``. A run
    that has not reported for ``stale_after`` — its process died — no longer
    holds its conversation: the next top-level run marks it failed and starts.
    Call ``watch`` right after ``start``: until then only the start time counts.
    A run taken for dead while its process was only slow is stopped at that
    process's next poll, so two runs of one conversation never go on together.
    """

    def __init__(
        self,
        *,
        clock: ClockInterface | None = None,
        cancel_poll_interval: float = DEFAULT_CANCEL_POLL_INTERVAL,
        heartbeat_interval: timedelta = DEFAULT_HEARTBEAT_INTERVAL,
        stale_after: timedelta = DEFAULT_STALE_AFTER,
    ) -> None:
        """Set the clock and timings every backend shares.

        Raises:
            InvalidConfigurationError: When an interval is not positive, or
                ``stale_after`` is not longer than ``heartbeat_interval`` and
                ``cancel_poll_interval`` — a heartbeat is written only when a
                poll runs, so a slower poll would make every live run look dead.
        """
        if cancel_poll_interval <= 0:
            raise InvalidConfigurationError("cancel_poll_interval must be positive.")
        if heartbeat_interval <= timedelta(0):
            raise InvalidConfigurationError("heartbeat_interval must be positive.")
        if stale_after <= heartbeat_interval:
            raise InvalidConfigurationError("stale_after must be longer than heartbeat_interval.")
        if stale_after <= timedelta(seconds=cancel_poll_interval):
            raise InvalidConfigurationError(
                "stale_after must be longer than cancel_poll_interval: a watched run reports "
                "itself alive only when it polls."
            )
        self._clock: ClockInterface = clock if clock is not None else SystemClock()
        self._cancel_poll_interval: float = cancel_poll_interval
        self._heartbeat_interval: timedelta = heartbeat_interval
        self._stale_after: timedelta = stale_after
        self._local_tokens: dict[str, CancellationToken] = {}

    @override
    async def start(
        self,
        run_id: str,
        *,
        agent: str,
        conversation_id: str | None = None,
        parent_run_id: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> RunStatus:
        """Record ``run_id`` as running; see :class:`~xtr_ai.RunControlInterface`.

        Raises:
            RunInProgressError: When the conversation already has a live
                top-level run in progress.
        """
        now: datetime = self._clock.now()
        status = RunStatus(
            run_id=run_id,
            agent=agent,
            state=RunState.RUNNING,
            conversation_id=conversation_id,
            parent_run_id=parent_run_id,
            metadata=MappingProxyType(dict(metadata or {})),
            started_at=now,
            heartbeat_at=now,
        )
        holder = await self._insert(status)
        if holder is None:
            return status
        if _elapsed(now, holder.heartbeat_at) > self._stale_after:
            _ = await self._finish(holder.run_id, RunState.FAILED, None, now)
            holder = await self._insert(status)
            if holder is None:
                return status
        raise RunInProgressError(conversation_id or "", holder.run_id)

    @override
    @asynccontextmanager
    async def watch(self, run_id: str, token: CancellationToken) -> AsyncGenerator[WatchedRun]:
        """Watch ``run_id`` while the block runs; see :class:`~xtr_ai.RunControlInterface`.

        Raises:
            UnknownRunError: When ``run_id`` was never started.
        """
        if await self._read(run_id) is None:
            raise UnknownRunError(run_id)
        watched = WatchedRun(run_id)
        self._local_tokens[run_id] = token
        # A plain task rather than a task group: a task group would wrap the block's own error
        # in an exception group, and the caller expects the error it raised.
        poller = asyncio.ensure_future(self._poll_until_ended(run_id, token, self._clock.now()))
        state = RunState.FAILED
        try:
            yield watched
            state = RunState.FINISHED
        except RunCancelled:
            state = RunState.CANCELLED
            raise
        except BaseException as error:
            if isinstance(error, anyio.get_cancelled_exc_class()):
                state = RunState.CANCELLED
            raise
        finally:
            _ = poller.cancel()
            _ = self._local_tokens.pop(run_id, None)
            with anyio.CancelScope(shield=True):
                _ = await asyncio.gather(poller, return_exceptions=True)
                _ = await self._finish(run_id, state, watched.usage, self._clock.now())

    @override
    async def get(self, run_id: str) -> RunStatus | None:
        """Return what is known of ``run_id``, or ``None`` if it was never started."""
        return await self._read(run_id)

    @override
    async def request_cancel(self, run_id: str) -> bool:
        """Ask for ``run_id`` to stop; return whether a running run was flagged."""
        flagged = await self._flag_cancel(run_id)
        token = self._local_tokens.get(run_id)
        if flagged and token is not None:
            # Watched in this process: no need to wait for the next poll.
            token.cancel()
        return flagged

    async def _poll_until_ended(
        self, run_id: str, token: CancellationToken, last_heartbeat: datetime
    ) -> None:
        while True:
            await anyio.sleep(self._cancel_poll_interval)
            now: datetime = self._clock.now()
            due = _elapsed(now, last_heartbeat) >= self._heartbeat_interval
            try:
                flagged = await self._poll(run_id, now if due else None)
            except Exception:  # noqa: BLE001, S112 — a store briefly unreachable must not end the watch
                # Stopping here would end the heartbeat for good, and the run would soon be
                # taken for dead while it runs. The next poll tries again, heartbeat included.
                continue
            if due:
                last_heartbeat = now
            if flagged:
                token.cancel()

    @abstractmethod
    async def _insert(self, status: RunStatus) -> RunStatus | None:
        """Store ``status`` unless its conversation is held; return the holder if it is.

        Only a top-level run with a conversation can be refused, and only by
        another running top-level run of that conversation — whatever its
        heartbeat: the caller decides whether a holder is stale. Must be atomic
        across every process sharing the backend.
        """

    @abstractmethod
    async def _read(self, run_id: str) -> RunStatus | None:
        """Return the stored run, or ``None``."""

    @abstractmethod
    async def _poll(self, run_id: str, heartbeat_at: datetime | None) -> bool:
        """Store ``heartbeat_at`` when given, and return whether the watched run must stop.

        It must when cancellation was asked for, and when the run is no longer
        running — another run took its conversation, taking it for dead.
        """

    @abstractmethod
    async def _flag_cancel(self, run_id: str) -> bool:
        """Flag a running run for cancellation; return whether one was running."""

    @abstractmethod
    async def _finish(
        self,
        run_id: str,
        state: RunState,
        usage: RunUsage | None,
        finished_at: datetime,
    ) -> bool:
        """Store ``state`` if the run is still running, releasing its conversation.

        Returns whether it was running — ``False`` when another terminal state
        was written first, which then stands.
        """


def _elapsed(later: datetime, earlier: datetime) -> timedelta:
    """The time from ``earlier`` to ``later``, as plain datetimes whatever the clock returns."""
    return later - earlier
