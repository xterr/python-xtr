"""Messages the tests send."""

from __future__ import annotations

from dataclasses import dataclass

from xtr_messenger import as_message


@as_message(name="tests.orm_messenger.order_placed.v1")
@dataclass(frozen=True, slots=True)
class OrderPlaced:
    order: str
