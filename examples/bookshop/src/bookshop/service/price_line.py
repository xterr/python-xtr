"""What one pricing rule did to a line."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

__all__ = ["PriceLine"]


@dataclass(frozen=True, slots=True)
class PriceLine:
    """What one rule did to a line.

    Attributes:
        rule: The rule's label.
        amount: The amount after it.
    """

    rule: str
    amount: Decimal
