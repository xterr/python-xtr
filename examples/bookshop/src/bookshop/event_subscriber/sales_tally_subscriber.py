"""A subscriber keeping a tally of every placed order."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from typing import final

from typing_extensions import override
from xtr_event_dispatcher import EventSubscriberInterface, SubscribedEvents

from bookshop.event.order_placed import OrderPlaced

__all__ = ["SalesTally"]


@final
class SalesTally(EventSubscriberInterface):
    """Counts the copies sold per book — a subscriber, one singleton for the process."""

    def __init__(self) -> None:
        """Start with nothing sold."""
        self.sold: Counter[str] = Counter()

    @classmethod
    @override
    def get_subscribed_events(cls) -> Mapping[str | type, SubscribedEvents]:
        return {OrderPlaced: "on_order_placed"}

    def on_order_placed(self, event: OrderPlaced) -> None:
        """Add the line's copies to its book's tally."""
        self.sold[event.isbn] += event.quantity
