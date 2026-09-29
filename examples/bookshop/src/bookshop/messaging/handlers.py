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

Every message is a unit of work: its handlers share one database session — through the
scoped repositories they ask for — and ``orm_transaction``, listed in ``config/messenger.py``,
commits what they wrote once they all succeeded, or rolls it back. No handler commits.
"""

from __future__ import annotations

from typing import Annotated, final

from xtr_dependency_injection import Autowire, Injected, Target
from xtr_logging_contracts import LoggerInterface
from xtr_messenger import (
    DispatchAfterCurrentBusStamp,
    Envelope,
    MessageBusInterface,
    ReceivedStamp,
    RedeliveryStamp,
    as_message_handler,
)
from xtr_rate_limiter import RateLimiterFactoryInterface

from bookshop.catalog import BookCatalogInterface
from bookshop.notifications import NotifierInterface
from bookshop.observability.security_audit_trail import SecurityAuditTrail
from bookshop.ordering import (
    Order,
    OrderRepository,
    OutOfStockError,
    Receipt,
    ReceiptRepository,
)
from fulltext import SearchEngineInterface

from .messages import AuditEvent, PlaceOrder, ReindexCatalog, SendReceipt, StockAlert
from .stamps import OriginStamp

__all__ = [
    "PlaceOrderHandler",
    "ReceiptCounter",
    "ReindexCatalogHandler",
    "page_purchasing",
    "record_audit_event",
    "send_receipt",
]

_FAST_SELLER = 3
_PER_ORDER = 12
_MAIL_WAIT = 30.0


@final
@as_message_handler(PlaceOrder)
class PlaceOrderHandler:
    """Records the order and dispatches what follows from it.

    Built once, by the container, with its constructor's dependencies — the bus included:
    a handler may dispatch further messages. The repository is the message's, on
    ``__call__``: a singleton cannot hold a scoped service.
    """

    def __init__(
        self,
        bus: MessageBusInterface,
        logger: Annotated[LoggerInterface, Target("orders")],
    ) -> None:
        """Dispatch through ``bus``; log to the ``orders`` channel."""
        self._bus = bus
        self._logger = logger

    async def __call__(
        self, message: PlaceOrder, envelope: Envelope, orders: Injected[OrderRepository]
    ) -> str:
        """Record ``message``, then ask for a receipt, an audit entry and maybe a stock alert.

        Returns:
            The order number — what a handler returns is recorded on its ``HandledStamp``,
            which ``orders:place`` prints.

        Raises:
            OutOfStockError: For more than twelve copies — after the order row was added, so
                ``orm_transaction`` rolls the row back: ``orders:place 978-0141439518 13``
                shows it.
        """
        _ = await orders.add(
            Order(
                id=message.order_id,
                number=message.number,
                isbn=message.isbn,
                quantity=message.quantity,
                email=message.email,
                total=message.total,
            )
        )
        if message.quantity > _PER_ORDER:
            raise OutOfStockError(message.isbn, message.quantity, _PER_ORDER)
        received = envelope.last(ReceivedStamp)
        self._logger.notice(
            "order {number} recorded via {transport}",
            {"number": message.number, "transport": received.transport_name if received else "-"},
        )
        # Held back until PlaceOrder was handled and orm_transaction committed the order: a
        # worker never reads a receipt's order before it exists, and an order rolled back
        # sends nothing.
        later = DispatchAfterCurrentBusStamp()
        _ = await self._bus.dispatch(
            SendReceipt(message.order_id, message.email, message.total),
            OriginStamp(message.number),
            later,
        )
        _ = await self._bus.dispatch(
            AuditEvent("order", f"{message.number} for {message.email}"), later
        )
        if message.quantity > _FAST_SELLER:
            _ = await self._bus.dispatch(StockAlert(message.isbn, message.quantity), later)
        return message.number


@as_message_handler(SendReceipt)
async def send_receipt(  # noqa: PLR0913, PLR0917 — the message, its envelope, and what the container provides.
    message: SendReceipt,
    envelope: Envelope,
    notifier: Injected[NotifierInterface],
    orders: Injected[OrderRepository],
    receipts: Injected[ReceiptRepository],
    currency: Annotated[str, Autowire(param="shop.currency")],
    mail_rate: Annotated[RateLimiterFactoryInterface, Target("outbound_mail")],
) -> None:
    """Mail the receipt and record it — a function handler, run by a worker.

    The order was committed by the unit of work that handled ``PlaceOrder`` before this
    message was sent; this message is a unit of its own, so the receipt row is committed — or
    rolled back — with it. A redelivered message whose receipt was recorded already records
    none again.

    The mail provider takes ten a minute (``outbound_mail``): the receipt reserves its slot and
    waits for it, up to half a minute — a limit outside any web route.

    Raises:
        ValueError: For an address under the reserved ``.invalid`` domain — which is how
            ``demo:errors`` shows a worker rejecting a message and carrying on.
        MaxWaitDurationExceededError: If the provider would make the receipt wait longer;
            the worker retries the message later, and nothing was reserved.
    """
    if message.email.endswith(".invalid"):
        raise ValueError(f"cannot mail {message.email}")
    order = await orders.get_one_or_none(id=message.order_id)
    attempt = envelope.last(RedeliveryStamp)
    origin = envelope.last(OriginStamp)  # declared with @as_stamp: it survives the transport
    received = envelope.last(ReceivedStamp)
    number = origin.order_number if origin else (order.number if order else str(message.order_id))
    retry = f" (retry {attempt.retry_count})" if attempt else ""
    transport = received.transport_name if received else "-"
    if not await receipts.exists(order_id=message.order_id, transport=transport):
        _ = await receipts.add(
            Receipt(order_id=message.order_id, email=message.email, transport=transport)
        )
    reservation = await mail_rate.create("provider").reserve(max_time=_MAIL_WAIT)
    await reservation.wait()
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
