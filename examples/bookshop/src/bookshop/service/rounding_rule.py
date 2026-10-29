"""The rounding pricing rule, placed ``after`` VAT — see ``pricing_rule``."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import ClassVar, final

from typing_extensions import override
from xtr_dependency_injection import as_alias, as_tagged_item

from bookshop.service.book import Book
from bookshop.service.pricing_rule import PricingRule
from bookshop.service.vat_rule import VatRule

__all__ = ["RoundingRule"]


@final
@as_alias(PricingRule, qualifier="rounding")
@as_tagged_item(index="rounding", after=[VatRule])
class RoundingRule(PricingRule):
    """Rounds to the cent, after the tax."""

    label: ClassVar[str] = "rounding"

    @override
    def apply(self, book: Book, quantity: int, amount: Decimal) -> Decimal:
        return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
