"""Listeners for every run, for every message a worker fails on, and for workers themselves.

The scheduler announces runs through the worker's events, so these hear runs whichever
worker handles them — the one consuming ``scheduler_default``, or one a run was sent to.
"""

from __future__ import annotations

from typing import Annotated

from xtr_dependency_injection import Target
from xtr_event_dispatcher import as_event_listener
from xtr_logging_contracts import LoggerInterface
from xtr_messenger.event import WorkerMessageFailedEvent, WorkerStartedEvent, WorkerStoppedEvent
from xtr_scheduler.event import FailureEvent, PostRunEvent

__all__ = [
    "report_failed_message",
    "report_failed_run",
    "report_run",
    "report_worker_started",
    "report_worker_stopped",
]


@as_event_listener()
async def report_run(
    event: PostRunEvent, logger: Annotated[LoggerInterface, Target("scheduler")]
) -> None:
    """Note what each run returned."""
    logger.notice(
        "{schedule}: {message} ran (due {due}) -> {result}",
        {
            "schedule": event.context.name,
            "message": str(event.message),
            "due": event.context.triggered_at.isoformat(timespec="seconds"),
            "result": repr(event.result),
        },
    )


@as_event_listener()
async def report_failed_run(
    event: FailureEvent, logger: Annotated[LoggerInterface, Target("scheduler")]
) -> None:
    """Note a run that failed; the worker deals with the failure itself."""
    logger.error(
        "{message} failed: {error}", {"message": str(event.message), "error": str(event.error)}
    )


@as_event_listener()
async def report_failed_message(
    event: WorkerMessageFailedEvent, logger: Annotated[LoggerInterface, Target("security")]
) -> None:
    """Any message a worker fails on — scheduled or not — with whether it will be retried."""
    logger.warning(
        "{transport} failed on {message}{retry}: {error}",
        {
            "transport": event.receiver_name,
            "message": type(event.envelope.message).__name__,
            "retry": " (retried)" if event.will_retry else "",
            "error": str(event.error),
        },
    )


@as_event_listener()
async def report_worker_started(
    event: WorkerStartedEvent, logger: Annotated[LoggerInterface, Target("scheduler")]
) -> None:
    """A worker is starting — every worker, the one ``orders:place`` drains with included."""
    logger.debug("worker {worker} started", {"worker": type(event.worker).__name__})


@as_event_listener()
async def report_worker_stopped(
    event: WorkerStoppedEvent, logger: Annotated[LoggerInterface, Target("scheduler")]
) -> None:
    """A worker stopped — however it came to."""
    logger.debug("worker {worker} stopped", {"worker": type(event.worker).__name__})
