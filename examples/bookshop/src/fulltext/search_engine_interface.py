"""What a search engine answers to — the seam an application depends on."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from .search_hit import SearchHit

__all__ = ["SearchEngineInterface"]


@runtime_checkable
class SearchEngineInterface(Protocol):
    """Indexes documents and answers queries against them."""

    def index(self, key: str, text: str, /) -> None:
        """Index ``text`` under ``key``, replacing what was there."""
        ...

    def search(self, query: str, /) -> list[SearchHit]:
        """Return the best hits for ``query``, best first."""
        ...
