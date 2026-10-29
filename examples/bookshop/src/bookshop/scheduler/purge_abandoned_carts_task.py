"""A function task in prod only, sent to ``jobs`` — see ``bookshop.scheduler``."""

from __future__ import annotations

from xtr_dependency_injection import Injected
from xtr_logging_contracts import LoggerInterface
from xtr_scheduler.decorator import as_cron_task

__all__ = ["purge_abandoned_carts"]


@as_cron_task("0 3 * * *", timezone="Europe/Bucharest", env="prod", transports="jobs")
async def purge_abandoned_carts(logger: Injected[LoggerInterface]) -> None:
    """Prod only; each run is sent to ``jobs`` and handled by the worker consuming it."""
    logger.info("abandoned carts purged")
