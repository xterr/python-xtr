"""``search:query`` and ``search:stats``: a function command and a class command."""

from __future__ import annotations

from typing import Annotated, final

from xtr_console import ConsoleStyle, ExitCode, Option, as_command, escape
from xtr_dependency_injection import Injected

from fulltext.analyzer_registry import AnalyzerRegistry
from fulltext.bundle.fulltext_config import FulltextConfig
from fulltext.search_engine_interface import SearchEngineInterface
from fulltext.search_index import SearchIndex

__all__ = ["SearchStatsCommand", "search_query"]


@as_command("search:query", aliases=("sq", "find"))
async def search_query(
    io: ConsoleStyle,
    query: str,
    engine: Injected[SearchEngineInterface],
    *,
    show_scores: Annotated[bool, Option(alias="-s")] = False,
) -> int:
    """Search the index.

    A function command: ``Injected[...]`` parameters come from the container, the style from
    the application, everything else from the command line.

    Args:
        io: Where the command writes.
        query: The words to look for.
        engine: The search engine, from the container.
        show_scores: Print each hit's score.
    """
    hits = engine.search(query)
    if not hits:
        io.warning(f"Nothing matches {escape(query)!r}.")
        return ExitCode.FAILURE
    headers = ["Key", "Score"] if show_scores else ["Key"]
    rows = [[hit.key, f"{hit.score:.2f}"] if show_scores else [hit.key] for hit in hits]
    io.table(headers, rows)
    return ExitCode.SUCCESS


@final
@as_command("search:stats")
class SearchStatsCommand:
    """Show what the index holds and how it analyzes text.

    A class command: the container builds it once, with its constructor's dependencies.
    """

    def __init__(
        self, index: SearchIndex, registry: AnalyzerRegistry, config: FulltextConfig
    ) -> None:
        """Report on ``index``, analyzed by the analyzers in ``registry``."""
        self._index = index
        self._registry = registry
        self._config = config

    async def __call__(self, io: ConsoleStyle, sample: str = "The Pragmatic Programmer") -> int:
        """Show the index size, the declared analyzers and what the pipeline makes of a sample.

        Args:
            io: Where the command writes.
            sample: Text to run through the pipeline.
        """
        io.title("Fulltext index")
        io.table(
            ["Setting", "Value"],
            [
                ["documents", str(self._index.size)],
                ["updated at", str(self._index.updated_at)],
                ["declared analyzers", ", ".join(self._registry.names())],
                ["pipeline", " -> ".join(self._config.pipeline)],
                ["max results", str(self._config.max_results)],
                ["min score", str(self._config.min_score)],
            ],
        )
        io.text(f"{escape(sample)!r} -> {self._index.terms(sample)!r}")
        return ExitCode.SUCCESS
