"""A stamp that travels: declared with ``@as_stamp``, restored after the transport."""

from __future__ import annotations

from dataclasses import dataclass
from typing import final

from xtr_messenger import StampInterface, as_stamp

__all__ = ["OriginStamp"]


@as_stamp
@final
@dataclass(frozen=True, slots=True)
class OriginStamp(StampInterface):
    """Which order a message follows from — sent with it, and restored on the other side.

    A transport restores only the stamps it knows: ``@as_stamp`` declares this one, so every
    serializer built without an explicit list restores it. ``jobs`` round-trips every
    message through the serializer (``?serialize=true``), so the receipt handler reading it
    back proves it survived; without the decorator it would silently be dropped.

    Attributes:
        order_number: The order the message follows from.
    """

    order_number: str
