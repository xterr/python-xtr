"""One line of a shopping cart."""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["CartLine"]


@dataclass(frozen=True, slots=True)
class CartLine:
    """One line of a cart.

    Attributes:
        isbn: The book.
        quantity: How many copies.
    """

    isbn: str
    quantity: int
