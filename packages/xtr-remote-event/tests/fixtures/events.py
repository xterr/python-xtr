"""Events an application derives from RemoteEvent, and a hierarchy of its own beside them.

Named here, at import, as an application names its events: before any message holding one is
written or read.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from xtr_serializer import ZonedDateTime, discriminator_map, discriminator_name

from xtr_remote_event import RemoteEvent

__all__ = ["DeliveryReport", "Notice", "Recipient", "StrayNotice", "UnnamedEvent"]


@dataclass(frozen=True, slots=True)
class Recipient:
    """A value nested in an event, carried as its own class."""

    address: str
    tags: tuple[str, ...] = ()


@discriminator_name("test_delivery_report")
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
    """An event whose class was never given a name, so nothing writes it."""

    reason: str = ""


@discriminator_map()
@dataclass(frozen=True, slots=True)
class Notice:
    """The base of a hierarchy that is not the remote events'."""

    text: str


@discriminator_name("test_stray_notice")
@dataclass(frozen=True, slots=True)
class StrayNotice(Notice):
    """A named class of that other hierarchy, whose name an event field must not take."""
