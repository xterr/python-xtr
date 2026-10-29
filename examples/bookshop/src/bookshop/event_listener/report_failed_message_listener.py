"""A listener for every message a worker fails on, scheduled or not."""

from __future__ import annotations

from typing import Annotated

from xtr_dependency_injection import Target
from xtr_event_dispatcher import as_event_listener
from xtr_logging_contracts import LoggerInterface
from xtr_messenger.event import WorkerMessageFailedEvent

__all__ = ["report_failed_message"]


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
