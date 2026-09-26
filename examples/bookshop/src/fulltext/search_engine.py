"""The default engine: an index, a result limit and a score threshold."""

from __future__ import annotations

from typing import TYPE_CHECKING

from typing_extensions import override

from .search_engine_interface import SearchEngineInterface

if TYPE_CHECKING:
    from xtr_logging_contracts import LoggerInterface

    from .query_log import QueryLog
    from .search_hit import SearchHit
    from .search_index import SearchIndex

__all__ = ["SearchEngine"]


class SearchEngine(SearchEngineInterface):
    """Searches one :class:`SearchIndex`, logging every query.

    Not ``@final``: :class:`~fulltext.bundle.timed_search_engine.TimedSearchEngine` decorates
    it, and a decorator must be of the decorated type.
    """

    def __init__(
        self,
        index: SearchIndex,
        max_results: int,
        min_score: float,
        logger: LoggerInterface,
        queries: QueryLog,
    ) -> None:
        """Search ``index``; return at most ``max_results`` hits scoring ``min_score`` or more."""
        self._index: SearchIndex = index
        self._max_results: int = max_results
        self._min_score: float = min_score
        self._logger: LoggerInterface = logger
        self._queries: QueryLog = queries

    @override
    def index(self, key: str, text: str, /) -> None:
        self._index.add(key, text)

    @override
    def search(self, query: str, /) -> list[SearchHit]:
        self._queries.record(query)
        hits = self._index.search(query, limit=self._max_results, min_score=self._min_score)
        self._logger.info("query {query} matched {count}", {"query": query, "count": len(hits)})
        return hits
