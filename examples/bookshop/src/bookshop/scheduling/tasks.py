"""Tasks: a class, methods of a class, and functions — run without writing a message.

Each run sends a ``ServiceCallMessage`` naming the target; the scheduler's handler calls it.
The container builds a task class with its dependencies, and a function task asks for
services with a marker, as any container-called function does.

=================================  ============================  ==========================
Target                             Trigger                       Where
=================================  ============================  ==========================
``heartbeat``                      every 2 s — dev and test      the scheduler's worker
``CatalogReport.build``            every 10 minutes, jittered    the scheduler's worker
``Housekeeping.forget_queries``    ``#daily``                    the scheduler's worker
``Housekeeping.reindex``           ``#weekly``, argument         the scheduler's worker
``purge_abandoned_carts``          03:00 Bucharest — prod only   sent to ``jobs``
=================================  ============================  ==========================
"""

from __future__ import annotations

from typing import Annotated, final

from xtr_dependency_injection import Injected, Target
from xtr_logging_contracts import LoggerInterface
from xtr_scheduler.decorator import as_cron_task, as_periodic_task

from bookshop.catalog import BookCatalogInterface
from fulltext import QueryLog, SearchEngineInterface

__all__ = ["CatalogReport", "Housekeeping", "heartbeat", "purge_abandoned_carts"]


@as_periodic_task(2, env=["dev", "test"])
async def heartbeat(logger: Annotated[LoggerInterface, Target("scheduler")]) -> str:
    """Say the schedule is alive — often, and outside prod only (``env=``)."""
    logger.info("heartbeat")
    return "alive"


@final
@as_periodic_task("10 minutes", jitter=30, method="build")
class CatalogReport:
    """A task class: built by the container, called through ``method``."""

    def __init__(
        self,
        catalog: BookCatalogInterface,
        logger: Annotated[LoggerInterface, Target("scheduler")],
    ) -> None:
        """Report on ``catalog``."""
        self._catalog = catalog
        self._logger = logger

    def build(self) -> int:
        """Count the catalog — the count is the run's result."""
        size = len(self._catalog.all())
        self._logger.info("catalog report: {size} titles", {"size": size})
        return size


@final
class Housekeeping:
    """Methods as tasks: each decorated method is a task of its own, calling that method."""

    def __init__(self, queries: QueryLog, engine: SearchEngineInterface) -> None:
        """Tidy the search library's query log and index."""
        self._queries = queries
        self._engine = engine

    @as_cron_task("#daily")
    def forget_queries(self) -> str:
        """Once a day, at a time hashed from the call it makes: empty the query log."""
        forgotten = len(self._queries.queries())
        self._queries.clear()
        return f"{forgotten} queries forgotten"

    @as_cron_task("#weekly", arguments=["weekly"])
    def reindex(self, reason: str) -> str:
        """Once a week, called with the declared argument: check the index still answers."""
        return f"{reason} check: {len(self._engine.search('the'))} hits for 'the'"


@as_cron_task("0 3 * * *", timezone="Europe/Bucharest", env="prod", transports="jobs")
async def purge_abandoned_carts(logger: Injected[LoggerInterface]) -> None:
    """Prod only; each run is sent to ``jobs`` and handled by the worker consuming it."""
    logger.info("abandoned carts purged")
