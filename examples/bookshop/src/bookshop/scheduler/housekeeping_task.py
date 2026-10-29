"""Methods as tasks, each a task of its own — see ``bookshop.scheduler``."""

from __future__ import annotations

from typing import final

from xtr_scheduler.decorator import as_cron_task

from fulltext import QueryLog, SearchEngineInterface

__all__ = ["Housekeeping"]


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
