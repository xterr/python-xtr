"""The declarations an application writes beside its consumers."""

from __future__ import annotations

from .as_remote_event_consumer import (
    as_remote_event_consumer,
    remote_event_consumers_declared_on,
)

__all__ = ["as_remote_event_consumer", "remote_event_consumers_declared_on"]
