"""The base of every pricing rule, carrying the application's own autoconfiguration.

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

The scan finds them in another order — by module name: the order comes from the decorators,
not from the source. A contradiction — ``before`` an item of lower priority — is a
``ServiceOrderError`` when the container compiles.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, ClassVar

from xtr_dependency_injection import autoconfigure_tag

if TYPE_CHECKING:
    from decimal import Decimal

    from bookshop.service.book import Book

__all__ = ["PRICING_RULE_TAG", "PricingRule"]

PRICING_RULE_TAG = "bookshop.pricing_rule"


# ``@autoconfigure_tag`` on a base class: every *registered* definition whose type has this
# class in its __mro__ gets the tag — here, the four rule classes.
# Repeatable — the second call, with no name, adds a tag named after the class itself (its
# qualified name). The base is never registered itself.
@autoconfigure_tag(PRICING_RULE_TAG, domain="pricing")
@autoconfigure_tag()
class PricingRule(ABC):
    """One step of pricing a line: a discount, a tax, a rounding."""

    label: ClassVar[str]

    @abstractmethod
    def apply(self, book: Book, quantity: int, amount: Decimal) -> Decimal:
        """Return ``amount`` after this rule, for ``quantity`` copies of ``book``."""
