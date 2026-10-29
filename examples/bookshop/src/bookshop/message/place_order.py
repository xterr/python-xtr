"""Placing an order: a message routed to ``sync``, its wire name pinned and versioned."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from xtr_messenger import as_message

__all__ = ["PlaceOrder"]


@as_message(name="bookshop.order.place.v1")
@dataclass(frozen=True, slots=True)
class PlaceOrder:
    """Record an order. Routed to ``sync``: handled during the dispatch, in this process."""

    order_id: UUID
    number: str
    isbn: str
    quantity: int
    email: str
    total: Decimal
