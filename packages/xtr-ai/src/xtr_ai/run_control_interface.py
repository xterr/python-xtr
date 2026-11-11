"""What an execution is doing now, and how to stop it from elsewhere."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Mapping
    from contextlib import AbstractAsyncContextManager

    from pydantic_ai import CancellationToken

    from xtr_ai.run_status import RunStatus
    from xtr_ai.watched_run import WatchedRun

__all__ = ["RunControlInterface"]


@runtime_checkable
class RunControlInterface(Protocol):
    """Tracks agent runs so another process can read and cancel them.

    Messages say what a run produced; they cannot say, while it is in flight,
    that it is running, nor stop it from another process. The process running
    the agent starts and watches the run; any process reads it or asks for it
    to stop::

        await run_control.start(run_id, agent="chat", conversation_id=conversation_id)
        token = CancellationToken()
        async with run_control.watch(run_id, token) as watched:
            result = await agent.run(prompt, run_id=run_id, cancellation_token=token)
            watched.record_usage(result.usage)

        # elsewhere
        await run_control.request_cancel(run_id)
    """

    async def start(
        self,
        run_id: str,
        *,
        agent: str,
        conversation_id: str | None = None,
        parent_run_id: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> RunStatus:
        """Record ``run_id`` as running.

        A conversation has at most one top-level run in progress; a run with a
        ``parent_run_id`` is delegated from another and is exempt.

        Raises:
            RunInProgressError: When the conversation already has a top-level
                run in progress.
        """
        ...

    def watch(
        self, run_id: str, token: CancellationToken
    ) -> AbstractAsyncContextManager[WatchedRun]:
        """Watch ``run_id`` while the block runs the agent.

        While inside, a cancellation asked for anywhere calls
        ``token.cancel()``. On the way out the run's terminal state is
        written — finished, cancelled (``RunCancelled`` or task cancellation)
        or failed (any other error) — shielded from cancellation, and the first
        terminal state written wins. The block's error, if any, propagates.

        Raises:
            UnknownRunError: When ``run_id`` was never started.
        """
        ...

    async def get(self, run_id: str) -> RunStatus | None:
        """Return what is known of ``run_id``, or ``None`` if it was never started."""
        ...

    async def request_cancel(self, run_id: str) -> bool:
        """Ask for ``run_id`` to stop; return whether a running run was flagged.

        Idempotent: asking again for a run still running answers ``True``; for
        an unknown or ended run, ``False``.
        """
        ...
