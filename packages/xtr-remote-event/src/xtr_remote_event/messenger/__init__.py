"""Consuming an event on a message bus: the message, and what handles it."""

from __future__ import annotations

from .consume_remote_event_handler import ConsumeRemoteEventHandler
from .consume_remote_event_message import ConsumeRemoteEventMessage

__all__ = ["ConsumeRemoteEventHandler", "ConsumeRemoteEventMessage"]
