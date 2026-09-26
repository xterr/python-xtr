"""The pricing rules, ordered with ``@as_tagged_item`` and collected through ``@as_alias``.

Each rule is a class. ``@as_tagged_item`` registers it — ``index`` becomes its qualifier,
``(VatRule, "vat")`` — and places it: ``priority`` first, highest first, then
``before``/``after`` among the items sharing a priority (one without a priority reads as 0).
``@as_alias(PricingRule, qualifier=index)`` makes it reachable as ``(PricingRule, "vat")``,
which is what puts it in ``Sequence[PricingRule]`` and ``Mapping[Hashable, PricingRule]``.
An alias takes its target's place, so the collection follows the rules' order:

=============  ========  ========  ======================
Rule           index     priority  constraint
=============  ========  ========  ======================
MemberRule     member    30        —
BulkRule       bulk      —         ``before=[VatRule]``
VatRule        vat       0         —
RoundingRule   rounding  —         ``after=[VatRule]``
=============  ========  ========  ======================

They are declared in another order on purpose: the order comes from the decorators, not from
the source. A contradiction — ``before`` an item of lower priority — is a
``ServiceOrderError`` when the container compiles.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated, ClassVar, final

from typing_extensions import override
from xtr_dependency_injection import Autowire, as_alias, as_tagged_item

from bookshop.catalog import Book, Genre

from .pricing_rule import PricingRule

__all__ = ["BulkRule", "MemberRule", "RoundingRule", "VatRule"]


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


@final
@as_alias(PricingRule, qualifier="rounding")
@as_tagged_item(index="rounding", after=[VatRule])
class RoundingRule(PricingRule):
    """Rounds to the cent, after the tax."""

    label: ClassVar[str] = "rounding"

    @override
    def apply(self, book: Book, quantity: int, amount: Decimal) -> Decimal:
        return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


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
