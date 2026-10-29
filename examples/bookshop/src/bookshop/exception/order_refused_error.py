"""An order the fraud check refused."""

from __future__ import annotations

from decimal import Decimal
from typing import final

from bookshop.exception.order_error import OrderError

__all__ = ["OrderRefusedError"]


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
