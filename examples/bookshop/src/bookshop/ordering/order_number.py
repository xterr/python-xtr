"""A transient service: a fresh value every time one is injected."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from xtr_clock import ClockInterface
from xtr_dependency_injection import as_service

__all__ = ["OrderNumber", "order_number"]


@dataclass(frozen=True, slots=True)
class OrderNumber:
    """A human-readable order number: the date, and a random suffix.

    Attributes:
        value: The number.
    """

    value: str


@as_service(lifetime="transient")
def order_number(clock: ClockInterface) -> OrderNumber:
    """Build a new number for every injection.

    ``lifetime="transient"``: never cached, not even within a scope. Like a scoped service it
    can only be built inside a scope — a command run, a web request — never from the root
    container with ``container.get``. The date comes from the injected clock, so a frozen
    clock freezes it.
    """
    return OrderNumber(f"BK-{clock.now():%Y%m%d}-{uuid4().hex[:6].upper()}")
