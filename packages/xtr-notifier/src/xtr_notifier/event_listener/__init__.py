"""Listeners the notifier ships.

``SendFailedMessageToNotifierListener`` needs xtr-messenger and is imported
from its own module, so importing this package needs no message bus.
"""

from __future__ import annotations

from .notification_logger_listener import NotificationLoggerListener

__all__ = ["NotificationLoggerListener"]
