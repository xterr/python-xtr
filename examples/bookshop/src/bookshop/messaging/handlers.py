"""Handlers, as functions and as classes, with every way of receiving what they need.

- The **message** is the first parameter; a second one annotated ``Envelope`` receives the
  envelope. Both are passed by the bus, by position.
- A **function handler** takes everything else from the container through a marker:
  ``Injected[T]``, ``Annotated[T, Target("q")]`` for a qualified service, or
  ``Annotated[T, Autowire(param=... | env=...)]``. A bare ``T`` is not injected.
- A **class handler** is a singleton the container builds: its constructor is injected
  like any service, and ``__call__`` takes what one message needs, with the same markers.

Every handler of a message runs, in declaration order, each leaving a ``HandledStamp``. The
messenger bundle binds them all at boot, so one asking for something the container cannot
provide fails the boot, not the first message.
"""

from __future__ import annotations

from typing import Annotated, final

from xtr_dependency_injection import Autowire, Injected, Target
from xtr_logging_contracts import LoggerInterface
from xtr_messenger import (
    Envelope,
    MessageBusInterface,
    ReceivedStamp,
    RedeliveryStamp,
    as_message_handler,
)

from bookshop.catalog import BookCatalogInterface
from bookshop.notifications import NotifierInterface
from bookshop.observability.security_audit_trail import SecurityAuditTrail
from bookshop.ordering import Order, OrderBook
from fulltext import SearchEngineInterface

from .messages import AuditEvent, PlaceOrder, ReindexCatalog, SendReceipt, StockAlert

__all__ = [
    "PlaceOrderHandler",
    "ReceiptCounter",
    "ReindexCatalogHandler",
    "page_purchasing",
    "record_audit_event",
    "send_receipt",
]

_FAST_SELLER = 3


@final
@as_message_handler(PlaceOrder)
class PlaceOrderHandler:
    """Records the order and dispatches what follows from it.

    Built once, by the container, with its constructor's dependencies — the bus included:
    a handler may dispatch further messages.
    """

    def __init__(
        self,
        orders: OrderBook,
        bus: MessageBusInterface,
        logger: Annotated[LoggerInterface, Target("orders")],
    ) -> None:
        """Record into ``orders``; dispatch through ``bus``."""
        self._orders = orders
        self._bus = bus
        self._logger = logger

    async def __call__(self, message: PlaceOrder, envelope: Envelope) -> None:
        """Record ``message``, then ask for a receipt, an audit entry and maybe a stock alert."""
        self._orders.record(
            Order(
                message.order_id,
                message.number,
                message.isbn,
                message.quantity,
                message.email,
                message.total,
            )
        )
        received = envelope.last(ReceivedStamp)
        self._logger.notice(
            "order {number} recorded via {transport}",
            {"number": message.number, "transport": received.transport_name if received else "-"},
        )
        _ = await self._bus.dispatch(SendReceipt(message.order_id, message.email, message.total))
        _ = await self._bus.dispatch(AuditEvent("order", f"{message.number} for {message.email}"))
        if message.quantity > _FAST_SELLER:
            _ = await self._bus.dispatch(StockAlert(message.isbn, message.quantity))


@as_message_handler(SendReceipt)
async def send_receipt(
    message: SendReceipt,
    envelope: Envelope,
    notifier: Injected[NotifierInterface],
    orders: Injected[OrderBook],
    currency: Annotated[str, Autowire(param="shop.currency")],
) -> None:
    """Mail the receipt — a function handler; which notifier depends on the environment.

    Raises:
        ValueError: For an address under the reserved ``.invalid`` domain — which is how
            ``demo:errors`` shows a worker rejecting a message and carrying on.
    """
    if message.email.endswith(".invalid"):
        raise ValueError(f"cannot mail {message.email}")
    order = orders.get(message.order_id)
    attempt = envelope.last(RedeliveryStamp)
    number = order.number if order else str(message.order_id)
    retry = f" (retry {attempt.retry_count})" if attempt else ""
    _ = notifier.notify(message.email, f"receipt for {number}: {message.total} {currency}{retry}")


@final
@as_message_handler(SendReceipt)
class ReceiptCounter:
    """A second handler of the same message: every handler runs."""

    def __init__(self) -> None:
        """Count from zero."""
        self.count = 0

    async def __call__(self, message: SendReceipt) -> None:
        """Count one more receipt."""
        del message
        self.count += 1


@final
@as_message_handler(ReindexCatalog)
class ReindexCatalogHandler:
    """Reindexes the catalog; what one message needs arrives on ``__call__``."""

    def __init__(self, catalog: BookCatalogInterface) -> None:
        """Read books from ``catalog``."""
        self._catalog = catalog

    async def __call__(
        self, message: ReindexCatalog, engine: Injected[SearchEngineInterface]
    ) -> None:
        """Index every book, or only the ISBNs the message names."""
        wanted = set(message.isbns)
        for book in self._catalog.all():
            if not wanted or book.isbn in wanted:
                engine.index(book.isbn, book.describe())


@as_message_handler(StockAlert)
async def page_purchasing(
    message: StockAlert,
    notifier: Annotated[NotifierInterface, Target("ops")],
) -> None:
    """Page purchasing through the qualified — and decorated — ``"ops"`` notifier."""
    _ = notifier.notify("purchasing", f"{message.isbn} sold {message.ordered} at once")


@as_message_handler(AuditEvent)
async def record_audit_event(message: AuditEvent, audit: Injected[SecurityAuditTrail]) -> None:
    """Write the audit trail."""
    audit.record(message.subject, message.detail)
