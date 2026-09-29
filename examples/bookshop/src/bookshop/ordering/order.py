"""A placed order, persisted: an advanced-alchemy model, one table row per order."""

from __future__ import annotations

from decimal import Decimal
from typing import final

from advanced_alchemy.base import UUIDAuditBase
from sqlalchemy import Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

__all__ = ["Order"]


@final
class Order(UUIDAuditBase):
    """One placed order.

    Its id, ``created_at`` and ``updated_at`` come from the base; the id is the one the
    ``PlaceOrder`` message carries, so a receipt handled later by a worker finds it.

    Attributes:
        number: The human-readable number.
        isbn: The book ordered.
        quantity: How many copies.
        email: Who ordered.
        total: What it costs, every pricing rule applied.
    """

    __tablename__ = "orders"

    number: Mapped[str] = mapped_column(String(32), unique=True)
    isbn: Mapped[str] = mapped_column(String(20), index=True)
    quantity: Mapped[int] = mapped_column()
    email: Mapped[str] = mapped_column(String(254))
    total: Mapped[Decimal] = mapped_column(Numeric(10, 2))
