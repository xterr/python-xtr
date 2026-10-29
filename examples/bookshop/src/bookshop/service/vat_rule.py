"""The VAT pricing rule — see ``pricing_rule`` for how the rules are ordered."""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, ClassVar, final

from typing_extensions import override
from xtr_dependency_injection import Autowire, as_alias, as_tagged_item

from bookshop.service.book import Book
from bookshop.service.pricing_rule import PricingRule

__all__ = ["VatRule"]


@final
@as_alias(PricingRule, qualifier="vat")
@as_tagged_item(index="vat", priority=0)
class VatRule(PricingRule):
    """Value added tax, applied after every discount; its rate is a parameter."""

    label: ClassVar[str] = "VAT"

    def __init__(self, rate: Annotated[float, Autowire(param="shop.vat_rate")]) -> None:
        """Add ``rate`` on top."""
        self._rate = Decimal(str(rate))

    @override
    def apply(self, book: Book, quantity: int, amount: Decimal) -> Decimal:
        return amount * (1 + self._rate)
