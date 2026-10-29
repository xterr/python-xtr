"""What scores how suspicious an order is."""

from __future__ import annotations

from decimal import Decimal
from typing import Protocol, runtime_checkable

__all__ = ["FraudCheckInterface"]


@runtime_checkable
class FraudCheckInterface(Protocol):
    """Scores how suspicious an order is, from 0 (fine) to 1 (refuse)."""

    def score(self, email: str, amount: Decimal, /) -> float:
        """Score an order of ``amount`` by ``email``."""
        ...
