"""A domain event: an order was placed."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from xtr_event_dispatcher_contracts import Event

__all__ = ["OrderPlaced"]


@dataclass(frozen=True)
class OrderPlaced(Event):
    """An order line was placed — dispatched by :class:`OrderService` to whoever listens.

    An ``Event``: a listener may stop it, and the listeners after it do not run. Frozen, and
    stoppable all the same — stopping is about the dispatch, not the data.

    Attributes:
        number: The order number.
        isbn: The book.
        quantity: How many copies.
        total: What it costs.
    """

    number: str
    isbn: str
    quantity: int
    total: Decimal
