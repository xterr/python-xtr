"""A book: one title in the catalog."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from bookshop.service.genre import Genre

__all__ = ["Book"]


@dataclass(frozen=True, slots=True)
class Book:
    """One title in the catalog.

    Attributes:
        isbn: The ISBN, the catalog's key.
        title: The title.
        author: The author.
        price: The price before any pricing rule.
        genre: Where it is shelved.
    """

    isbn: str
    title: str
    author: str
    price: Decimal
    genre: Genre

    def describe(self) -> str:
        """Return the text the search index holds for this book."""
        return f"{self.title} {self.author} {self.genre} {self.isbn}"
