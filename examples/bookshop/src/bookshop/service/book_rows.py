"""The rows the catalog commands print and export."""

from __future__ import annotations

from collections.abc import Sequence

from bookshop.service.book import Book

__all__ = ["book_rows"]


def book_rows(books: Sequence[Book]) -> list[dict[str, str]]:
    """The four columns every exporter and the table share."""
    return [
        {"isbn": b.isbn, "title": b.title, "author": b.author, "price": str(b.price)} for b in books
    ]
