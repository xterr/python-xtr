"""A service removed because its package is not installed."""

from __future__ import annotations

from typing import final

from xtr_dependency_injection import as_service, remove_if_missing

from .book_catalog_interface import BookCatalogInterface

__all__ = ["RedisCatalogWarmer"]


@final
@remove_if_missing(package="redis")
@as_service
class RedisCatalogWarmer:
    """Would copy the catalog into Redis; dropped, because the ``redis`` distribution is absent.

    ``package=`` names a *distribution* (what ``pip`` installs), checked with
    ``importlib.metadata`` when the container compiles. Install ``redis`` and the service
    appears — ``bookshop di:show`` reports ``has(RedisCatalogWarmer)``.
    """

    def __init__(self, catalog: BookCatalogInterface) -> None:
        """Warm from ``catalog``."""
        self._catalog = catalog

    def warm(self) -> int:
        """Copy every book; return how many."""
        return len(self._catalog.all())
