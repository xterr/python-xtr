"""Books, the catalog that holds them, and the decorators stacked around it."""

from __future__ import annotations

from .book import Book, Genre
from .book_catalog_interface import BookCatalogInterface

__all__ = ["Book", "BookCatalogInterface", "Genre"]
