"""Who hears about a placed order first: a function listener of priority 10.

It runs before ``SalesTally``, the subscriber keeping a tally of the same event.
"""

from __future__ import annotations

from typing import Annotated

from xtr_dependency_injection import Target
from xtr_event_dispatcher import as_event_listener
from xtr_logging_contracts import LoggerInterface

from bookshop.event.order_placed import OrderPlaced

__all__ = ["log_order_placed"]


@as_event_listener(priority=10)
async def log_order_placed(
    event: OrderPlaced, logger: Annotated[LoggerInterface, Target("orders")]
) -> None:
    """Log every placed line — the event type comes from the annotation."""
    logger.info(
        "order {number}: {quantity} x {isbn}",
        {"number": event.number, "quantity": event.quantity, "isbn": event.isbn},
    )
