"""A listener for every worker starting."""

from __future__ import annotations

from typing import Annotated

from xtr_dependency_injection import Target
from xtr_event_dispatcher import as_event_listener
from xtr_logging_contracts import LoggerInterface
from xtr_messenger.event import WorkerStartedEvent

__all__ = ["report_worker_started"]


@as_event_listener()
async def report_worker_started(
    event: WorkerStartedEvent, logger: Annotated[LoggerInterface, Target("scheduler")]
) -> None:
    """A worker is starting — every worker, the one ``orders:place`` drains with included."""
    logger.debug("worker {worker} started", {"worker": type(event.worker).__name__})
