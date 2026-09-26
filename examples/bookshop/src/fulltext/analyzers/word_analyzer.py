"""Splitting text into words."""

from __future__ import annotations

import re
from typing import Final, cast, final

from typing_extensions import override

from fulltext.analyzer_interface import AnalyzerInterface
from fulltext.decorator import as_analyzer

__all__ = ["WordAnalyzer"]

_WORD: Final = re.compile(r"[\w-]+")


@final
@as_analyzer("words")
class WordAnalyzer(AnalyzerInterface):
    """Splits every term on anything that is not a word character or a hyphen."""

    @override
    def analyze(self, terms: list[str], /) -> list[str]:
        return [word for term in terms for word in cast("list[str]", _WORD.findall(term))]
