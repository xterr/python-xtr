"""Stamps of the application's own: two kept in the process, one that travels."""

from __future__ import annotations

from dataclasses import dataclass
from typing import final

from xtr_messenger import NonSendableStampInterface, StampInterface, as_stamp

__all__ = ["DispatchTimeStamp", "MaintenanceStamp", "OriginStamp"]


@final
@dataclass(frozen=True, slots=True)
class DispatchTimeStamp(NonSendableStampInterface):
    """How long the rest of the chain took, recorded by ``TimingMiddleware``.

    ``NonSendableStampInterface``: stripped before the envelope reaches a transport, so it
    never travels on the wire — a local measurement means nothing to a consumer.

    Attributes:
        milliseconds: The duration.
    """

    milliseconds: float


@final
@dataclass(frozen=True, slots=True)
class MaintenanceStamp(NonSendableStampInterface):
    """Marks a dispatch the maintenance guard refused.

    Attributes:
        reason: Why.
    """

    reason: str


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
