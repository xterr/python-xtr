"""The listener reporting failed messages, built only when the bus is there to fail them."""

from __future__ import annotations

from xtr_notifier.event_listener.send_failed_message_to_notifier_listener import (
    SendFailedMessageToNotifierListener,
)
from xtr_notifier.notifier_interface import NotifierInterface

__all__ = ["failed_message_listener"]


def failed_message_listener(notifier: NotifierInterface) -> SendFailedMessageToNotifierListener:
    """Report every message the bus gives up on through ``notifier``."""
    return SendFailedMessageToNotifierListener(notifier)
