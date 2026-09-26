"""The analyzers the library ships, declared with its own ``@as_analyzer``.

This package is the bundle's ``resources``: the kernel scans it early, like the application,
so the bundle's autoconfiguration sees each declared class.
"""

from __future__ import annotations

from .lowercase_analyzer import LowercaseAnalyzer
from .stop_word_analyzer import StopWordAnalyzer
from .word_analyzer import WordAnalyzer

__all__ = ["LowercaseAnalyzer", "StopWordAnalyzer", "WordAnalyzer"]
