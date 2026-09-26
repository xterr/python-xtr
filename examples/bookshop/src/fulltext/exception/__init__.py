"""Everything the library raises: one base error, one error per module."""

from __future__ import annotations

from .fulltext_error import FulltextError
from .unknown_analyzer_error import UnknownAnalyzerError

__all__ = ["FulltextError", "UnknownAnalyzerError"]
