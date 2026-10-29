"""An order for more copies than one order may take."""

from __future__ import annotations

from typing import final

from bookshop.exception.order_error import OrderError

__all__ = ["OutOfStockError"]


@final
class OutOfStockError(OrderError):
    """A handler of ``PlaceOrder`` could not reserve the copies ordered.

    Raised inside the message's unit of work, it rolls back what every handler of the
    message wrote — the order row included.

    Attributes:
        isbn: The book.
        quantity: How many copies were asked for.
        available: How many one order may take.
    """

    def __init__(self, isbn: str, quantity: int, available: int) -> None:
        """Name the book and the shortfall."""
        self.isbn = isbn
        self.quantity = quantity
        self.available = available
        super().__init__(f"only {available} copies of {isbn} per order, {quantity} asked for")
