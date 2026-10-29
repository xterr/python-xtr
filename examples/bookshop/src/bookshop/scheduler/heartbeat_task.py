"""A function task, every two seconds, outside prod only — see ``bookshop.scheduler``."""

from __future__ import annotations

from typing import Annotated

from xtr_dependency_injection import Target
from xtr_logging_contracts import LoggerInterface
from xtr_scheduler.decorator import as_periodic_task

__all__ = ["heartbeat"]


@as_periodic_task(2, env=["dev", "test"])
async def heartbeat(logger: Annotated[LoggerInterface, Target("scheduler")]) -> str:
    """Say the schedule is alive — often, and outside prod only (``env=``)."""
    logger.info("heartbeat")
    return "alive"
