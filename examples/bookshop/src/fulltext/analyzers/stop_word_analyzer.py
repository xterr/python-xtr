"""Dropping words too common to rank by."""

from __future__ import annotations

from typing import final

from typing_extensions import override

from fulltext.analyzer_interface import AnalyzerInterface
from fulltext.bundle.fulltext_config import FulltextConfig
from fulltext.decorator import as_analyzer

__all__ = ["StopWordAnalyzer"]


@final
@as_analyzer("stop_words")
class StopWordAnalyzer(AnalyzerInterface):
    """Drops every configured stop word.

    Its constructor asks for the library's own config: the kernel registers every active
    bundle's resolved config under its type, so any service can inject it.
    """

    def __init__(self, config: FulltextConfig) -> None:
        """Drop the words ``config.stop_words`` lists."""
        self._stop_words = frozenset(word.casefold() for word in config.stop_words)

    @override
    def analyze(self, terms: list[str], /) -> list[str]:
        return [term for term in terms if term.casefold() not in self._stop_words]
