"""A listener for every worker stopping."""

from __future__ import annotations

from typing import Annotated

from xtr_dependency_injection import Target
from xtr_event_dispatcher import as_event_listener
from xtr_logging_contracts import LoggerInterface
from xtr_messenger.event import WorkerStoppedEvent

__all__ = ["report_worker_stopped"]


@as_event_listener()
async def report_worker_stopped(
    event: WorkerStoppedEvent, logger: Annotated[LoggerInterface, Target("scheduler")]
) -> None:
    """A worker stopped — however it came to."""
    logger.debug("worker {worker} stopped", {"worker": type(event.worker).__name__})
