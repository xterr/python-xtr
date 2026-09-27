"""The shop's own scheduled message."""

from __future__ import annotations

from dataclasses import dataclass

from typing_extensions import override
from xtr_messenger import as_message

__all__ = ["RestockCheck"]


@as_message(name="bookshop.stock.restock_check.v1")
@dataclass(frozen=True, slots=True)
class RestockCheck:
    """Check which titles run low.

    It has a string form of its own: a hashed cron expression (``#hourly``) picks its minute
    from it, so the shop's checks land at a minute of their own rather than on the hour
    with everyone else's.

    Attributes:
        scope: Which titles — a label only.
    """

    scope: str

    @override
    def __str__(self) -> str:
        return f"restock check ({self.scope})"
