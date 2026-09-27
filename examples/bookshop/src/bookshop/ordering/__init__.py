"""Orders: a scoped unit of work, a transient order number, a scoped cart, and the service."""

from __future__ import annotations

from .order import Order, OrderBook
from .order_listeners import SalesTally, log_order_placed
from .order_number import OrderNumber
from .order_placed import OrderPlaced
from .order_service import OrderService
from .request_scoped import RequestScoped, ShoppingCart
from .unit_of_work import UnitOfWork

__all__ = [
    "Order",
    "OrderBook",
    "OrderNumber",
    "OrderPlaced",
    "OrderService",
    "RequestScoped",
    "SalesTally",
    "ShoppingCart",
    "UnitOfWork",
    "log_order_placed",
]
