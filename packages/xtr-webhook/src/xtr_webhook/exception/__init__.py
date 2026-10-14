"""Every error this library raises.

All of them derive from :class:`WebhookError`, so one ``except`` catches anything a
webhook can go wrong with, and a narrower one handles a single cause. Each carries what
went wrong as typed attributes rather than forcing a message to be parsed — and none of
them repeats a secret.
"""

from __future__ import annotations

from .delivery_error import DeliveryError
from .invalid_argument_error import InvalidArgumentError
from .logic_error import LogicError
from .reject_webhook_error import RejectWebhookError
from .webhook_error import WebhookError
from .webhook_runtime_error import WebhookRuntimeError

__all__ = [
    "DeliveryError",
    "InvalidArgumentError",
    "LogicError",
    "RejectWebhookError",
    "WebhookError",
    "WebhookRuntimeError",
]
