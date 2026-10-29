"""A fast-selling title: a message declaring a list of transports."""

from __future__ import annotations

from dataclasses import dataclass

from xtr_messenger import as_message

__all__ = ["StockAlert"]


# The wire name it travelled under before it moved here, pinned so it does not change.
@as_message(name="bookshop.messaging.messages:StockAlert", transport=["outbox"])
@dataclass(frozen=True, slots=True)
class StockAlert:
    """Tell purchasing a title sells fast. Declares a list of transports — one here."""

    isbn: str
    ordered: int
