"""The application extending a library: an analyzer declared with the library's decorator.

``fulltext`` knows nothing about ISBNs. Declaring one more analyzer with ``@as_analyzer``
in a scanned module is all it takes: the library's bundle finds it like its own, and the
application's config puts it in the pipeline.
"""

from __future__ import annotations

from typing import final

from typing_extensions import override

from fulltext import AnalyzerInterface, as_analyzer

__all__ = ["IsbnAnalyzer"]


@final
@as_analyzer("isbn")
class IsbnAnalyzer(AnalyzerInterface):
    """Adds the digits-only form of an ISBN, so ``9780135957059`` finds ``978-0135957059``."""

    @override
    def analyze(self, terms: list[str], /) -> list[str]:
        extra = [term.replace("-", "") for term in terms if term[:1].isdigit() and "-" in term]
        return [*terms, *extra]
