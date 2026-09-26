"""A placed order, and the book of orders the process keeps."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import final
from uuid import UUID

from xtr_dependency_injection import as_service

__all__ = ["Order", "OrderBook"]


@dataclass(frozen=True, slots=True)
class Order:
    """One placed order.

    Attributes:
        order_id: Its id.
        number: The human-readable number.
        isbn: The book ordered.
        quantity: How many copies.
        email: Who ordered.
        total: What it costs, every pricing rule applied.
    """

    order_id: UUID
    number: str
    isbn: str
    quantity: int
    email: str
    total: Decimal


@final
@as_service
class OrderBook:
    """Every order this process placed — a singleton, so it outlives any one command."""

    __slots__ = ("_orders",)

    def __init__(self) -> None:
        """Start empty."""
        self._orders: dict[UUID, Order] = {}

    def record(self, order: Order) -> None:
        """Keep ``order``."""
        self._orders[order.order_id] = order

    def get(self, order_id: UUID) -> Order | None:
        """The order ``order_id``, if placed."""
        return self._orders.get(order_id)

    def all(self) -> tuple[Order, ...]:
        """Every order, in the order placed."""
        return tuple(self._orders.values())
