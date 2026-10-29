"""``orders:list`` — a class command, its repositories per run."""

from __future__ import annotations

from typing import final

from xtr_console import ConsoleStyle, ExitCode, as_command
from xtr_dependency_injection import Injected

from bookshop.repository.order_repository import OrderRepository
from bookshop.repository.receipt_repository import ReceiptRepository

__all__ = ["OrdersListCommand"]


@final
@as_command("orders:list")
class OrdersListCommand:
    """List the orders in the database — a class command, its repositories per run.

    The command is a singleton; the repositories — and the session under them — are this
    run's, on ``__call__``, released when the run ends.
    """

    async def __call__(
        self,
        io: ConsoleStyle,
        orders: Injected[OrderRepository],
        receipts: Injected[ReceiptRepository],
    ) -> int:
        """List the orders, newest first, with how many receipts each has.

        Args:
            io: Where the command writes.
            orders: This run's order repository.
            receipts: This run's receipt repository.
        """
        placed = await orders.list(order_by=[("created_at", True)])
        if not placed:
            io.note("No orders yet — run orm:migrations:migrate once, then orders:place.")
            return ExitCode.SUCCESS
        rows: list[list[str]] = []
        for order in placed:
            sent = await receipts.count(order_id=order.id)
            rows.append(
                [order.number, order.isbn, str(order.quantity), str(order.total), str(sent)]
            )
        io.table(["Number", "ISBN", "Qty", "Total", "Receipts"], rows)
        return ExitCode.SUCCESS
