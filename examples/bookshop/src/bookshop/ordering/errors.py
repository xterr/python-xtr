"""What placing an order can refuse — one base error, carrying its data as attributes."""

from __future__ import annotations

from decimal import Decimal
from typing import final

__all__ = ["OrderError", "OrderRefusedError", "UnknownBookError"]


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
