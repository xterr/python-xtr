"""The base of every pricing rule, carrying the application's own autoconfiguration."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, ClassVar

from xtr_dependency_injection import autoconfigure_tag

if TYPE_CHECKING:
    from decimal import Decimal

    from bookshop.catalog import Book

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
