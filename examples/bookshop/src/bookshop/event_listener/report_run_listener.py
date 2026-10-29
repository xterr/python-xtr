"""A listener for every scheduled run.

The scheduler announces runs through the worker's events, so the listeners here hear runs
whichever worker handles them — the one consuming ``scheduler_default``, or one a run was
sent to.
"""

from __future__ import annotations

from typing import Annotated

from xtr_dependency_injection import Target
from xtr_event_dispatcher import as_event_listener
from xtr_logging_contracts import LoggerInterface
from xtr_scheduler.event import PostRunEvent

__all__ = ["report_run"]


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
