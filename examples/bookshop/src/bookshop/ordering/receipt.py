"""A receipt sent for an order, persisted — one per transport it was sent through."""

from __future__ import annotations

from typing import final
from uuid import UUID

from advanced_alchemy.base import BigIntAuditBase
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

__all__ = ["Receipt"]


@final
class Receipt(BigIntAuditBase):
    """A receipt, written by the handler that mails it — inside the same transaction.

    Attributes:
        order_id: The order it is for.
        email: Where it went.
        transport: The transport the ``SendReceipt`` message arrived from: it is fanned out
            to two, so each order gets two receipts.
    """

    __tablename__ = "receipts"

    order_id: Mapped[UUID] = mapped_column(ForeignKey("orders.id"), index=True)
    email: Mapped[str] = mapped_column(String(254))
    transport: Mapped[str] = mapped_column(String(64))
