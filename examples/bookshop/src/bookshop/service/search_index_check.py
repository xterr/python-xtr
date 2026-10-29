"""A startup check at priority 0 — see ``startup_check`` for the order they run in."""

from __future__ import annotations

from typing import final

from typing_extensions import override
from xtr_dependency_injection import as_tagged_item

from bookshop.service.book_catalog_interface import BookCatalogInterface
from bookshop.service.startup_check import StartupCheck
from fulltext import SearchEngineInterface

__all__ = ["SearchIndexCheck"]


@final
@as_tagged_item(priority=0)
class SearchIndexCheck(StartupCheck):
    """Indexes every book, so the first search already finds something."""

    def __init__(self, catalog: BookCatalogInterface, engine: SearchEngineInterface) -> None:
        """Index ``catalog`` into ``engine``."""
        self._catalog = catalog
        self._engine = engine

    @override
    async def run(self) -> str:
        books = self._catalog.all()
        for book in books:
            self._engine.index(book.isbn, book.describe())
        return f"indexed {len(books)} books"
