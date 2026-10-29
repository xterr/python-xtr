"""A listener for every scheduled run that failed — see ``report_run_listener``."""

from __future__ import annotations

from typing import Annotated

from xtr_dependency_injection import Target
from xtr_event_dispatcher import as_event_listener
from xtr_logging_contracts import LoggerInterface
from xtr_scheduler.event import FailureEvent

__all__ = ["report_failed_run"]


@as_event_listener()
async def report_failed_run(
    event: FailureEvent, logger: Annotated[LoggerInterface, Target("scheduler")]
) -> None:
    """Note a run that failed; the worker deals with the failure itself."""
    logger.error(
        "{message} failed: {error}", {"message": str(event.message), "error": str(event.error)}
    )
