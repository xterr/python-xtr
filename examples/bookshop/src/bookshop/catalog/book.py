"""A book, and the genres the shop shelves books under."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

__all__ = ["Book", "Genre"]


class Genre(StrEnum):
    """Where a book is shelved."""

    FICTION = "fiction"
    SOFTWARE = "software"
    HISTORY = "history"


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
