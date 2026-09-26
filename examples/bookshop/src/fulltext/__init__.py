"""A small full-text search library: analyzers turn text into terms, an index ranks documents.

It knows nothing about the bookshop. It is laid out the way every reusable package in this
ecosystem is — one public class per file, ``*_interface.py`` protocols, an ``exception/``
package with one base error, and a ``bundle/`` package integrating it with a kernel — so it
doubles as the template for writing a library that ships its own bundle.

The library works without a container::

    index = SearchIndex([LowercaseAnalyzer(), WordAnalyzer()], SystemClock())
    index.add("b1", "The Pragmatic Programmer")
    engine = SearchEngine(index, 5, 0.0, NullLogger(), QueryLog())
    engine.search("pragmatic")

The bundle only decides what goes into a container.
"""

from __future__ import annotations

from .analyzer_interface import AnalyzerInterface
from .decorator import as_analyzer
from .exception import FulltextError, UnknownAnalyzerError
from .query_log import QueryLog
from .search_engine import SearchEngine
from .search_engine_interface import SearchEngineInterface
from .search_hit import SearchHit
from .search_index import SearchIndex

__all__ = [
    "AnalyzerInterface",
    "FulltextError",
    "QueryLog",
    "SearchEngine",
    "SearchEngineInterface",
    "SearchHit",
    "SearchIndex",
    "UnknownAnalyzerError",
    "as_analyzer",
]
