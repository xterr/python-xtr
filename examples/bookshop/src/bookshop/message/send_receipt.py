"""Mailing a receipt: a message the routing table fans out to two transports."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from xtr_messenger import as_message

__all__ = ["SendReceipt"]


@as_message(name="bookshop.order.receipt.v1")
@dataclass(frozen=True, slots=True)
class SendReceipt:
    """Mail the customer a receipt. Fanned out to ``jobs`` and ``audit``."""

    order_id: UUID
    email: str
    total: Decimal
