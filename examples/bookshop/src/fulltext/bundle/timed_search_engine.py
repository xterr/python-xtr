"""A decorator the bundle wraps around the engine: it times every query."""

from __future__ import annotations

from typing import Annotated, final

from typing_extensions import override
from xtr_clock import MonotonicClock
from xtr_dependency_injection import AutowireDecorated

from fulltext.search_engine import SearchEngine
from fulltext.search_hit import SearchHit

__all__ = ["TimedSearchEngine"]


@final
class TimedSearchEngine(SearchEngine):
    """Wraps the engine and records queries slower than a threshold.

    Registered by the bundle with ``services.set(TimedSearchEngine).set_decorated_service(
    SearchEngine)``: it takes the engine's place under its key, and receives the original
    through the one parameter annotated ``Annotated[SearchEngine, AutowireDecorated()]``.
    ``threshold_ms`` is given with ``set_argument`` — a plain value, or an ``env()``
    placeholder resolved when the engine is built.

    Durations come from a :class:`~xtr_clock.MonotonicClock`: a wall clock may jump while a
    query runs, a monotonic one never does.
    """

    def __init__(  # pyright: ignore[reportMissingSuperCall] — a wrapper, not a second engine.
        self,
        inner: Annotated[SearchEngine, AutowireDecorated()],
        threshold_ms: float,
    ) -> None:
        """Delegate to ``inner``; record queries slower than ``threshold_ms``."""
        # SearchEngine.__init__ is deliberately not called: this wraps an engine rather than
        # being one, and subclasses only because a decorator must be of the decorated type.
        self._inner = inner
        self._threshold_ms = threshold_ms
        self._clock = MonotonicClock()
        self.slow_queries: list[tuple[str, float]] = []

    @override
    def index(self, key: str, text: str, /) -> None:
        self._inner.index(key, text)

    @override
    def search(self, query: str, /) -> list[SearchHit]:
        started = self._clock.now()
        hits = self._inner.search(query)
        elapsed_ms = (self._clock.now() - started).total_seconds() * 1000
        if elapsed_ms > self._threshold_ms:
            self.slow_queries.append((query, elapsed_ms))
        return hits
