"""The bulk discount pricing rule, placed ``before`` VAT — see ``pricing_rule``."""

from __future__ import annotations

from decimal import Decimal
from typing import ClassVar, final

from typing_extensions import override
from xtr_dependency_injection import as_alias, as_tagged_item

from bookshop.service.book import Book
from bookshop.service.genre import Genre
from bookshop.service.pricing_rule import PricingRule
from bookshop.service.vat_rule import VatRule

__all__ = ["BulkRule"]


@final
@as_alias(PricingRule, qualifier="bulk")
@as_tagged_item(index="bulk", before=[VatRule])
class BulkRule(PricingRule):
    """Ten percent off five copies or more of a software book, before the tax."""

    label: ClassVar[str] = "bulk discount"

    @override
    def apply(self, book: Book, quantity: int, amount: Decimal) -> Decimal:
        if book.genre is Genre.SOFTWARE and quantity >= 5:  # noqa: PLR2004 — the rule itself.
            return amount * Decimal("0.9")
        return amount
