"""A scoped service by inheritance: a subclass of ``RequestScoped``."""

from __future__ import annotations

from typing import final

from xtr_dependency_injection import as_service

from bookshop.service.cart_line import CartLine
from bookshop.service.request_scoped import RequestScoped

__all__ = ["ShoppingCart"]


@final
@as_service
class ShoppingCart(RequestScoped):
    """What one request is buying; a new one every scope."""

    __slots__ = ("lines",)

    def __init__(self) -> None:
        """Start empty."""
        self.lines: list[CartLine] = []

    def add(self, isbn: str, quantity: int) -> None:
        """Add ``quantity`` copies of ``isbn``."""
        self.lines.append(CartLine(isbn, quantity))
