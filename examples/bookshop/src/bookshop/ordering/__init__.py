"""Orders: the persisted orders and receipts, their repositories, and what places them.

A scoped unit of work, a transient order number and a scoped cart show the container's
lifetimes; the orders themselves live in the database, written by the message handlers.
"""

from __future__ import annotations

from .errors import OutOfStockError
from .order import Order
from .order_listeners import SalesTally, log_order_placed
from .order_number import OrderNumber
from .order_placed import OrderPlaced
from .order_repository import OrderRepository
from .order_service import OrderService
from .receipt import Receipt
from .receipt_repository import ReceiptRepository
from .request_scoped import RequestScoped, ShoppingCart
from .unit_of_work import UnitOfWork

__all__ = [
    "Order",
    "OrderNumber",
    "OrderPlaced",
    "OrderRepository",
    "OrderService",
    "OutOfStockError",
    "Receipt",
    "ReceiptRepository",
    "RequestScoped",
    "SalesTally",
    "ShoppingCart",
    "UnitOfWork",
    "log_order_placed",
]
