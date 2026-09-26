"""Documents by key, reduced to the terms the analyzers produce."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from .search_hit import SearchHit

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_clock import ClockInterface, DatePoint

    from .analyzer_interface import AnalyzerInterface

__all__ = ["SearchIndex"]


@final
class SearchIndex:
    """An in-memory inverted index, shared by every unit of work of the process."""

    __slots__ = ("_analyzers", "_clock", "_documents", "_updated_at")

    def __init__(self, analyzers: Sequence[AnalyzerInterface], clock: ClockInterface) -> None:
        """Analyze with ``analyzers``, in order; stamp updates with ``clock``."""
        self._analyzers = tuple(analyzers)
        self._clock = clock
        self._documents: dict[str, frozenset[str]] = {}
        self._updated_at: DatePoint | None = None

    @property
    def size(self) -> int:
        """How many documents are indexed."""
        return len(self._documents)

    @property
    def updated_at(self) -> DatePoint | None:
        """When a document was last added, by the injected clock."""
        return self._updated_at

    def terms(self, text: str) -> list[str]:
        """Return what the analyzers make of ``text``."""
        terms = [text]
        for analyzer in self._analyzers:
            terms = analyzer.analyze(terms)
        return terms

    def add(self, key: str, text: str) -> None:
        """Index ``text`` under ``key``."""
        self._documents[key] = frozenset(self.terms(text))
        self._updated_at = self._clock.now()

    def search(self, query: str, *, limit: int, min_score: float) -> list[SearchHit]:
        """Return up to ``limit`` hits scoring at least ``min_score``, best first."""
        wanted = frozenset(self.terms(query))
        if not wanted:
            return []
        hits = [
            SearchHit(key, len(wanted & terms) / len(wanted))
            for key, terms in self._documents.items()
        ]
        ranked = sorted(
            (hit for hit in hits if hit.score > 0 and hit.score >= min_score),
            key=lambda hit: (-hit.score, hit.key),
        )
        return ranked[:limit]

    def clear(self) -> None:
        """Forget every document."""
        self._documents.clear()
        self._updated_at = None
