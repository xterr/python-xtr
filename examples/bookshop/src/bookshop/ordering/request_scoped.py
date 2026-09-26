"""A marker base whose subclasses are scoped, by ``@autoconfigure(lifetime=...)``."""

from __future__ import annotations

from dataclasses import dataclass
from typing import final

from xtr_dependency_injection import as_service, autoconfigure

__all__ = ["CartLine", "RequestScoped", "ShoppingCart"]


@autoconfigure(lifetime="scoped", tags=["bookshop.request_scoped"])
class RequestScoped:
    """Every registered subclass lives for one scope: one command run, one web request.

    The rule sets the lifetime of every matching definition, so a subclass needs only
    ``@as_service`` — it cannot forget to be scoped.
    """


@dataclass(frozen=True, slots=True)
class CartLine:
    """One line of a cart.

    Attributes:
        isbn: The book.
        quantity: How many copies.
    """

    isbn: str
    quantity: int


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
