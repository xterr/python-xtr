"""An order naming a book the catalog does not hold."""

from __future__ import annotations

from typing import final

from bookshop.exception.order_error import OrderError

__all__ = ["UnknownBookError"]


@final
class UnknownBookError(OrderError, LookupError):
    """The ISBN names no book in the catalog.

    Attributes:
        isbn: The ISBN asked for.
    """

    def __init__(self, isbn: str) -> None:
        """Name the ISBN."""
        self.isbn = isbn
        super().__init__(f"no book with ISBN {isbn}")
