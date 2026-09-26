"""Applying every pricing rule, in collection order."""

from __future__ import annotations

from collections.abc import Hashable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Annotated, final

from xtr_dependency_injection import Autowire, as_service

from bookshop.catalog import Book

from .pricing_rule import PricingRule

__all__ = ["PriceCalculator", "PriceLine"]


@dataclass(frozen=True, slots=True)
class PriceLine:
    """What one rule did to a line.

    Attributes:
        rule: The rule's label.
        amount: The amount after it.
    """

    rule: str
    amount: Decimal


@final
@as_service
class PriceCalculator:
    """Prices a line through every rule.

    Two collections of the same services: ``Sequence[PricingRule]`` in collection order,
    ``Mapping[Hashable, PricingRule]`` keyed by each rule's qualifier (its ``index``).
    """

    __slots__ = ("_by_index", "_currency", "_rules")

    def __init__(
        self,
        rules: Sequence[PricingRule],
        by_index: Mapping[Hashable, PricingRule],
        currency: Annotated[str, Autowire(param="shop.currency")],
    ) -> None:
        """Apply ``rules`` in order; price in ``currency``."""
        self._rules = tuple(rules)
        self._by_index = dict(by_index)
        self._currency = currency

    @property
    def currency(self) -> str:
        """The currency every amount is in."""
        return self._currency

    def indexes(self) -> tuple[Hashable, ...]:
        """Every rule's index, as the mapping keys them."""
        return tuple(self._by_index)

    def price(self, book: Book, quantity: int) -> list[PriceLine]:
        """Return the line's amount after each rule, the last being the total."""
        amount = book.price * quantity
        lines = [PriceLine("list price", amount)]
        for rule in self._rules:
            amount = rule.apply(book, quantity, amount)
            lines.append(PriceLine(rule.label, amount))
        return lines
