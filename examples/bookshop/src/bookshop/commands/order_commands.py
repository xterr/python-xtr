"""``orders:*`` — scoped and transient services per run, the bus, and draining a worker."""

from __future__ import annotations

from typing import Annotated, final

from xtr_console import Argument, ConsoleStyle, ExitCode, Option, Range, as_command, escape
from xtr_dependency_injection import Injected
from xtr_messenger import (
    Envelope,
    HandledStamp,
    MessageBusInterface,
    SentStamp,
    TransportMessageIdStamp,
    TransportNamesStamp,
    WorkerFactory,
)

from bookshop.messaging.messages import ReindexCatalog
from bookshop.messaging.stamps import DispatchTimeStamp, MaintenanceStamp
from bookshop.ordering import OrderBook, OrderNumber, OrderService, ShoppingCart, UnitOfWork
from bookshop.ordering.errors import OrderError

__all__ = ["OrdersListCommand", "place_order", "reindex_catalog"]

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
) -> int:
    """Place an order, then run a worker over what it queued.

    The cart and the unit of work are scoped — built for this run, released when it ends
    (the unit of work commits then); the order number is transient. ``PlaceOrder`` goes to
    ``sync://`` and is handled during the dispatch; what its handler dispatches in turn is
    queued on ``in-memory://`` and ``outbox://`` until the worker drains it.

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
    """
    customer = email or io.ask("Customer e-mail?", "reader@bookshop.example")
    cart.add(isbn, quantity)
    try:
        envelopes = await orders.place(cart, customer, number, work)
    except OrderError as error:
        io.error(escape(str(error)))
        return ExitCode.FAILURE
    for envelope in envelopes:
        _describe(io, envelope)
    if drain:
        for name in io.progress(_QUEUED, description="Draining"):
            await workers.worker([name]).run()
    io.success(f"Order {number.value} placed ({len(work.changes)} line).")
    return ExitCode.SUCCESS


@as_command("orders:reindex")
async def reindex_catalog(
    io: ConsoleStyle,
    reason: str = "manual",
    *,
    via: str | None = None,
    bus: Injected[MessageBusInterface],
    workers: Injected[WorkerFactory],
) -> int:
    """Ask for a reindex — a pydantic message — optionally forcing its transport.

    Args:
        io: Where the command writes.
        reason: Why (three characters or more: the model validates it).
        via: A transport to send it through instead of the one it declares; a
            ``TransportNamesStamp`` on the envelope beats the routing table.
        bus: The bus.
        workers: Builds the worker that handles it.
    """
    stamps = [TransportNamesStamp((via,))] if via else []
    envelope = await bus.dispatch(ReindexCatalog(reason=reason), *stamps)
    _describe(io, envelope)
    target = via or "jobs"
    if target != "sync":  # sync:// handled it during the dispatch: nothing is queued there.
        await workers.worker([target]).run()
    io.success("Catalog reindexed.")
    return ExitCode.SUCCESS


@final
@as_command("orders:list")
class OrdersListCommand:
    """List the orders this process placed — a class command with a singleton dependency."""

    def __init__(self, orders: OrderBook) -> None:
        """Read ``orders``."""
        self._orders = orders

    async def __call__(self, io: ConsoleStyle) -> int:
        """List the orders.

        Args:
            io: Where the command writes.
        """
        placed = self._orders.all()
        if not placed:
            io.note("No orders in this process yet — try orders:place.")
            return ExitCode.SUCCESS
        io.table(
            ["Number", "ISBN", "Qty", "Total"],
            [[o.number, o.isbn, str(o.quantity), str(o.total)] for o in placed],
        )
        return ExitCode.SUCCESS


def _describe(io: ConsoleStyle, envelope: Envelope) -> None:
    """Print what the chain recorded on ``envelope``, stamp by stamp."""
    refused = envelope.last(MaintenanceStamp)
    if refused is not None:
        io.warning(f"{type(envelope.message).__name__} refused: {refused.reason}")
        return
    timing = envelope.last(DispatchTimeStamp)
    io.listing(
        [
            f"message: {type(envelope.message).__name__}",
            *(f"sent via {s.sender_alias}" for s in envelope.all(SentStamp)),
            *(f"transport id {s.message_id}" for s in envelope.all(TransportMessageIdStamp)),
            *(f"handled by {s.handler_name}" for s in envelope.all(HandledStamp)),
            f"dispatch took {timing.milliseconds:.2f} ms" if timing else "not timed",
        ]
    )
