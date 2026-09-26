"""Placing orders: a singleton that takes the per-scope services as call arguments."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, final
from uuid import uuid4

from xtr_dependency_injection import Target, as_service
from xtr_logging_contracts import LoggerInterface
from xtr_messenger import MessageBusInterface

from bookshop.catalog import BookCatalogInterface
from bookshop.messaging.messages import PlaceOrder
from bookshop.payments import FraudCheckInterface
from bookshop.pricing import PriceCalculator

from .errors import OrderRefusedError, UnknownBookError

if TYPE_CHECKING:
    from xtr_messenger import Envelope

    from .order_number import OrderNumber
    from .request_scoped import ShoppingCart
    from .unit_of_work import UnitOfWork

__all__ = ["OrderService"]


@final
@as_service
class OrderService:
    """Prices a cart, checks it, and dispatches one ``PlaceOrder`` per line.

    A singleton cannot depend on a scoped or transient service — the container refuses it —
    so the cart, the unit of work and the order number are *arguments*, injected into the
    command or controller that calls :meth:`place`.
    """

    __slots__ = ("_bus", "_calculator", "_catalog", "_fraud", "_logger")

    def __init__(
        self,
        catalog: BookCatalogInterface,
        calculator: PriceCalculator,
        fraud: FraudCheckInterface,
        bus: MessageBusInterface,
        logger: Annotated[LoggerInterface, Target("orders")],
    ) -> None:
        """Collaborate with the catalog, the pricing rules, the fraud check and the bus."""
        self._catalog = catalog
        self._calculator = calculator
        self._fraud = fraud
        self._bus = bus
        self._logger = logger

    async def place(
        self, cart: ShoppingCart, email: str, number: OrderNumber, work: UnitOfWork
    ) -> list[Envelope]:
        """Dispatch every line of ``cart`` as an order numbered ``number``.

        Raises:
            UnknownBookError: If a line names a book the catalog does not hold.
            OrderRefusedError: If the fraud check refuses a line.
        """
        envelopes: list[Envelope] = []
        for line in cart.lines:
            book = self._catalog.find(line.isbn)
            if book is None:
                raise UnknownBookError(line.isbn)
            total = self._calculator.price(book, line.quantity)[-1].amount
            if self._fraud.score(email, total) >= 1.0:
                self._logger.warning("order refused", {"email": email, "total": str(total)})
                raise OrderRefusedError(email, total)
            message = PlaceOrder(uuid4(), number.value, book.isbn, line.quantity, email, total)
            envelopes.append(await self._bus.dispatch(message))
            work.record(f"{number.value}: {line.quantity} x {book.title}")
        return envelopes
