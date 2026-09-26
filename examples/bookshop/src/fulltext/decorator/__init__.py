"""The library's own declaration decorator, read by its bundle's autoconfiguration."""

from __future__ import annotations

from .as_analyzer import AnalyzerDeclaration, analyzers_declared_on, as_analyzer

__all__ = ["AnalyzerDeclaration", "analyzers_declared_on", "as_analyzer"]
