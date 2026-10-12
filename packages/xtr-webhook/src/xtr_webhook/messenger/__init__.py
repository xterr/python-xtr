"""Sending a webhook on a message bus: the message, and what handles it.

Delivering through the bus rather than inline is what gives sending everything the
bus already has — retries with a delay, a dead-letter place for what stays refused,
and a worker pool to do the waiting — without this library growing a retry policy of
its own.
"""

from __future__ import annotations

from .send_webhook_handler import SendWebhookHandler
from .send_webhook_message import SendWebhookMessage

__all__ = ["SendWebhookHandler", "SendWebhookMessage"]
