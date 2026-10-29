"""The handler of ``ReindexCatalog``: a class handler taking per-message services on the call."""

from __future__ import annotations

from typing import final

from xtr_dependency_injection import Injected
from xtr_messenger import as_message_handler

from bookshop.message.reindex_catalog import ReindexCatalog
from bookshop.service.book_catalog_interface import BookCatalogInterface
from fulltext import SearchEngineInterface

__all__ = ["ReindexCatalogHandler"]


@final
@as_message_handler(ReindexCatalog)
class ReindexCatalogHandler:
    """Reindexes the catalog; what one message needs arrives on ``__call__``."""

    def __init__(self, catalog: BookCatalogInterface) -> None:
        """Read books from ``catalog``."""
        self._catalog = catalog

    async def __call__(
        self, message: ReindexCatalog, engine: Injected[SearchEngineInterface]
    ) -> None:
        """Index every book, or only the ISBNs the message names."""
        wanted = set(message.isbns)
        for book in self._catalog.all():
            if not wanted or book.isbn in wanted:
                engine.index(book.isbn, book.describe())
