"""The fulltext library's config — and, through its ``AliasOf`` field, the clock's."""

from __future__ import annotations

from xtr_clock.bundle import ClockConfig
from xtr_dependency_injection import configure, env

from fulltext.bundle import FulltextConfig

__all__ = ["fulltext"]


@configure
def fulltext() -> FulltextConfig:
    """Configure search; forward a clock config to the clock bundle.

    Numbers come from ``env()`` with a type and a default: while the kernel builds, the
    placeholder *is* that default, so ``FulltextConfig.__post_init__`` validates a plausible
    value; the resolved copy the engine receives is validated again.
    """
    return FulltextConfig(
        # "isbn" is the application's own analyzer (bookshop.search), declared with the
        # library's @as_analyzer and picked up by the library's bundle.
        pipeline=("lowercase", "words", "stop_words", "isbn"),
        stop_words=("the", "and", "of", "a"),
        max_results=env("SEARCH_MAX_RESULTS", int, default=10),
        min_score=env("SEARCH_MIN_SCORE", float, default=0.25),
        slow_query_ms=env("SEARCH_SLOW_QUERY_MS", float, default=25.0),
        clock=ClockConfig(timezone=env("APP_TIMEZONE", default="Europe/Bucharest")),
    )
