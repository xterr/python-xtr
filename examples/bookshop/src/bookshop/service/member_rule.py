"""The members' discount pricing rule, of the highest priority — see ``pricing_rule``."""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, ClassVar, final

from typing_extensions import override
from xtr_dependency_injection import Autowire, as_alias, as_tagged_item

from bookshop.service.book import Book
from bookshop.service.pricing_rule import PricingRule

__all__ = ["MemberRule"]


@final
@as_alias(PricingRule, qualifier="member")
@as_tagged_item(index="member", priority=30)
class MemberRule(PricingRule):
    """A members' discount, its rate read from the environment when the rule is built."""

    label: ClassVar[str] = "member discount"

    def __init__(self, rate: Annotated[float, Autowire(env="float:SHOP_MEMBER_DISCOUNT")]) -> None:
        """Take ``rate`` (``0.05`` is 5%) off every line."""
        self._rate = Decimal(str(rate))

    @override
    def apply(self, book: Book, quantity: int, amount: Decimal) -> Decimal:
        return amount * (1 - self._rate)
