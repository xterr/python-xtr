"""The handler of ``PlaceOrder``: a class handler that dispatches what follows from an order."""

from __future__ import annotations

from typing import Annotated, final

from xtr_dependency_injection import Injected, Target
from xtr_logging_contracts import LoggerInterface
from xtr_messenger import (
    DispatchAfterCurrentBusStamp,
    Envelope,
    MessageBusInterface,
    ReceivedStamp,
    as_message_handler,
)

from bookshop.entity.order import Order
from bookshop.exception.out_of_stock_error import OutOfStockError
from bookshop.message.audit_event import AuditEvent
from bookshop.message.place_order import PlaceOrder
from bookshop.message.send_receipt import SendReceipt
from bookshop.message.stock_alert import StockAlert
from bookshop.repository.order_repository import OrderRepository
from bookshop.stamp.origin_stamp import OriginStamp

__all__ = ["PlaceOrderHandler"]

_FAST_SELLER = 3
_PER_ORDER = 12


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
