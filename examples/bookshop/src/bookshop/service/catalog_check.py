"""A startup check placed ``before`` another — see ``startup_check`` for the order."""

from __future__ import annotations

from typing import final

from typing_extensions import override
from xtr_dependency_injection import as_tagged_item

from bookshop.service.book_catalog_interface import BookCatalogInterface
from bookshop.service.search_index_check import SearchIndexCheck
from bookshop.service.startup_check import StartupCheck

__all__ = ["CatalogCheck"]


@final
@as_tagged_item(before=[SearchIndexCheck])
class CatalogCheck(StartupCheck):
    """The catalog is not empty — before anything indexes it."""

    def __init__(self, catalog: BookCatalogInterface) -> None:
        """Check ``catalog``."""
        self._catalog = catalog

    @override
    async def run(self) -> str:
        count = len(self._catalog.all())
        if count == 0:
            raise RuntimeError("the catalog is empty")
        return f"{count} books in the catalog"
