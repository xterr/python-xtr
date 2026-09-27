"""Who hears about a placed order: a function listener, and a subscriber keeping a tally.

Neither is registered by hand. The event dispatcher bundle finds ``@as_event_listener``
functions and every ``EventSubscriberInterface`` class in the scan, and hands them to the
container's dispatcher in priority order — the listener here runs first (priority 10).
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from typing import Annotated, final

from typing_extensions import override
from xtr_dependency_injection import Target
from xtr_event_dispatcher import EventSubscriberInterface, SubscribedEvents, as_event_listener
from xtr_logging_contracts import LoggerInterface

from .order_placed import OrderPlaced

__all__ = ["SalesTally", "log_order_placed"]


@as_event_listener(priority=10)
async def log_order_placed(
    event: OrderPlaced, logger: Annotated[LoggerInterface, Target("orders")]
) -> None:
    """Log every placed line — the event type comes from the annotation."""
    logger.info(
        "order {number}: {quantity} x {isbn}",
        {"number": event.number, "quantity": event.quantity, "isbn": event.isbn},
    )


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
