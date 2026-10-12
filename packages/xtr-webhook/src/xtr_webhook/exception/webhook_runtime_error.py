"""Something a webhook depends on failed while it was being handled."""

from __future__ import annotations

from .webhook_error import WebhookError

__all__ = ["WebhookRuntimeError"]


class WebhookRuntimeError(WebhookError, RuntimeError):
    """Something a webhook depends on failed while it was handled — a receiver that refuses.

    The input was fine and the code is fine; the world did not cooperate. Raising
    one out of a message handler is what makes a message bus retry the delivery and,
    once it has run out of attempts, keep the message rather than drop it.
    """
