"""Events an application derives from RemoteEvent.

Named here, at import, as an application names its events: before any message carrying one is
sent or read.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from xtr_remote_event import RemoteEvent
from xtr_serializer import ZonedDateTime, discriminator_name

__all__ = ["DeliveryReport", "Recipient", "UnnamedEvent"]


@dataclass(frozen=True, slots=True)
class Recipient:
    """A value nested in an event, carried as its own class."""

    address: str
    tags: tuple[str, ...] = ()


@discriminator_name("webhook_test_delivery_report")
@dataclass(frozen=True, slots=True)
class DeliveryReport(RemoteEvent):
    """An application's event: dates, a nested value, tags and metadata beside the payload."""

    occurred_at: datetime
    scheduled_for: ZonedDateTime
    recipient: Recipient
    tags: tuple[str, ...] = ()
    metadata: dict[str, str] = field(default_factory=dict[str, str])


@dataclass(frozen=True, slots=True)
class UnnamedEvent(RemoteEvent):
    """An event whose class was never given a name, so no message carries it."""

    reason: str = ""
