"""Run control held in this process's memory."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, final

from typing_extensions import override

from xtr_ai.abstract_run_control import (
    DEFAULT_CANCEL_POLL_INTERVAL,
    DEFAULT_HEARTBEAT_INTERVAL,
    DEFAULT_STALE_AFTER,
    AbstractRunControl,
)

if TYPE_CHECKING:
    from datetime import datetime, timedelta

    from pydantic_ai.usage import RunUsage
    from xtr_clock import ClockInterface

    from xtr_ai.run_state import RunState
    from xtr_ai.run_status import RunStatus

__all__ = ["InMemoryRunControl"]


@final
class InMemoryRunControl(AbstractRunControl):
    """Runs tracked in memory: one process only, for tests and inline runs.

    A cancellation reaches a run watched by this same instance at once, without
    waiting for a poll. Nothing survives the process, and another process sees
    nothing. Every run is kept for the life of the process, so a long-running
    one that starts many runs wants a backend that stores them elsewhere.
    """

    def __init__(
        self,
        *,
        clock: ClockInterface | None = None,
        cancel_poll_interval: float = DEFAULT_CANCEL_POLL_INTERVAL,
        heartbeat_interval: timedelta = DEFAULT_HEARTBEAT_INTERVAL,
        stale_after: timedelta = DEFAULT_STALE_AFTER,
    ) -> None:
        """Start empty, with :class:`AbstractRunControl`'s clock and timings."""
        super().__init__(
            clock=clock,
            cancel_poll_interval=cancel_poll_interval,
            heartbeat_interval=heartbeat_interval,
            stale_after=stale_after,
        )
        self._runs: dict[str, RunStatus] = {}
        self._holders: dict[str, str] = {}

    @override
    async def _insert(self, status: RunStatus) -> RunStatus | None:
        conversation_id = status.conversation_id
        if status.holds_conversation and conversation_id is not None:
            holder = self._holders.get(conversation_id)
            if holder is not None:
                return self._runs[holder]
            self._holders[conversation_id] = status.run_id
        self._runs[status.run_id] = status
        return None

    @override
    async def _read(self, run_id: str) -> RunStatus | None:
        return self._runs.get(run_id)

    @override
    async def _poll(self, run_id: str, heartbeat_at: datetime | None) -> bool:
        status = self._runs[run_id]
        if heartbeat_at is not None and status.is_running:
            status = self._runs[run_id] = replace(status, heartbeat_at=heartbeat_at)
        return status.cancel_requested or not status.is_running

    @override
    async def _flag_cancel(self, run_id: str) -> bool:
        status = self._runs.get(run_id)
        if status is None or not status.is_running:
            return False
        self._runs[run_id] = replace(status, cancel_requested=True)
        return True

    @override
    async def _finish(
        self,
        run_id: str,
        state: RunState,
        usage: RunUsage | None,
        finished_at: datetime,
    ) -> bool:
        status = self._runs.get(run_id)
        if status is None or not status.is_running:
            return False
        self._runs[run_id] = replace(status, state=state, usage=usage, finished_at=finished_at)
        if (
            status.conversation_id is not None
            and self._holders.get(status.conversation_id) == run_id
        ):
            del self._holders[status.conversation_id]
        return True
