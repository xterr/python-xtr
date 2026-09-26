"""Case-folding every term."""

from __future__ import annotations

from typing import final

from typing_extensions import override

from fulltext.analyzer_interface import AnalyzerInterface
from fulltext.decorator import as_analyzer

__all__ = ["LowercaseAnalyzer"]


@final
@as_analyzer("lowercase")
class LowercaseAnalyzer(AnalyzerInterface):
    """Folds case, so a query matches whatever the document's capitalisation."""

    @override
    def analyze(self, terms: list[str], /) -> list[str]:
        return [term.casefold() for term in terms]
