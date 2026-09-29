"""What placing an order can refuse — one base error, carrying its data as attributes."""

from __future__ import annotations

from decimal import Decimal
from typing import final

__all__ = ["OrderError", "OrderRefusedError", "OutOfStockError", "UnknownBookError"]


class OrderError(Exception):
    """Every ordering error derives from this one."""


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


@final
class OrderRefusedError(OrderError):
    """The fraud check refused the order.

    Attributes:
        email: Who ordered.
        total: What the order came to.
    """

    def __init__(self, email: str, total: Decimal) -> None:
        """Name the customer and the amount."""
        self.email = email
        self.total = total
        super().__init__(f"order of {total} by {email} refused by the fraud check")


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
