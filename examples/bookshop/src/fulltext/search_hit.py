"""One ranked result."""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["SearchHit"]


@dataclass(frozen=True, slots=True)
class SearchHit:
    """A document key and how well it matched, between 0 and 1.

    Attributes:
        key: The key the document was indexed under.
        score: The share of the query's terms the document contains.
    """

    key: str
    score: float
