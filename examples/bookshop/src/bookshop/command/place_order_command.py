"""``orders:place`` — scoped and transient services per run, the bus, and draining a worker."""

from __future__ import annotations

from typing import Annotated

from xtr_console import Argument, ConsoleStyle, ExitCode, Option, Range, as_command, escape
from xtr_dependency_injection import Injected
from xtr_messenger import HandlersFailedError, WorkerFactory

from bookshop.event_subscriber.sales_tally_subscriber import SalesTally
from bookshop.exception.order_error import OrderError
from bookshop.service.describe_envelope import describe_envelope
from bookshop.service.order_number import OrderNumber
from bookshop.service.order_service import OrderService
from bookshop.service.shopping_cart import ShoppingCart
from bookshop.service.unit_of_work import UnitOfWork

__all__ = ["place_order"]

_QUEUED = ("jobs", "audit", "outbox")


@as_command("orders:place", aliases=("order", "op"))
async def place_order(  # noqa: PLR0913 — the command line plus what the container provides.
    io: ConsoleStyle,
    isbn: str,
    quantity: Annotated[int, Argument(validator=Range(gte=1, lte=50))] = 1,
    *,
    email: Annotated[str, Option(env_var="BOOKSHOP_CUSTOMER_EMAIL")] = "",
    drain: Annotated[bool, Option(negative="--no-drain")] = True,
    cart: Injected[ShoppingCart],
    work: Injected[UnitOfWork],
    number: Injected[OrderNumber],
    orders: Injected[OrderService],
    workers: Injected[WorkerFactory],
    tally: Injected[SalesTally],
) -> int:
    """Place an order, then run a worker over what it queued.

    The cart and the unit of work are scoped — built for this run, released when it ends
    (the unit of work commits then); the order number is transient. ``PlaceOrder`` goes to
    ``sync://`` and is handled during the dispatch; what its handler dispatches in turn is
    queued on ``in-memory://`` and ``outbox://`` until the worker drains it.

    Each message is a database transaction of its own: the order row is committed once
    ``PlaceOrder`` is handled — and only then are its follow-ups sent, held back by a
    ``DispatchAfterCurrentBusStamp`` — each receipt once the worker handled its
    ``SendReceipt``. Over twelve copies, the handler refuses after writing the order row: the
    row is rolled back and nothing is sent — ``orders:list`` shows it never landed.

    Args:
        io: Where the command writes.
        isbn: The book.
        quantity: How many copies.
        email: The customer; ``$BOOKSHOP_CUSTOMER_EMAIL`` when omitted, else asked for.
        drain: Run a worker over the queued transports (``--no-drain`` to leave them).
        cart: This run's cart.
        work: This run's unit of work.
        number: A fresh order number.
        orders: The order service.
        workers: Builds workers over the configured transports.
        tally: What the ``OrderPlaced`` subscriber counted.
    """
    customer = email or io.ask("Customer e-mail?", "reader@bookshop.example")
    cart.add(isbn, quantity)
    try:
        envelopes = await orders.place(cart, customer, number, work)
    except OrderError as error:
        io.error(escape(str(error)))
        return ExitCode.FAILURE
    except HandlersFailedError as error:
        failures = "; ".join(f"{name}: {failure}" for name, failure in error.errors.items())
        io.error(f"Order {number.value} rolled back — {escape(failures)}")
        return ExitCode.FAILURE
    for envelope in envelopes:
        describe_envelope(io, envelope)
    if drain:
        for name in io.progress(_QUEUED, description="Draining"):
            await workers.worker([name]).run()
    io.text(f"Copies of {escape(isbn)} sold in this process: {tally.sold[isbn]}.")
    io.success(f"Order {number.value} placed ({len(work.changes)} line).")
    return ExitCode.SUCCESS
