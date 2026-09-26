"""A pipeline names an analyzer nothing declared."""

from __future__ import annotations

from typing import final

from .fulltext_error import FulltextError

__all__ = ["UnknownAnalyzerError"]


@final
class UnknownAnalyzerError(FulltextError, LookupError):
    """The configured pipeline names an analyzer no ``@as_analyzer`` class declares.

    Attributes:
        name: The unknown analyzer.
        known: Every analyzer that is declared.
    """

    def __init__(self, name: str, known: tuple[str, ...]) -> None:
        """Name the analyzer and what is declared instead."""
        self.name = name
        self.known = known
        super().__init__(f"no analyzer named {name!r}; declared: {', '.join(known) or 'none'}")
