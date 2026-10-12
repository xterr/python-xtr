"""A value handed to this library cannot be used."""

from __future__ import annotations

from .webhook_error import WebhookError

__all__ = ["InvalidArgumentError"]


class InvalidArgumentError(WebhookError, ValueError):
    """A value handed to this library cannot be used: a signature format, an empty secret.

    Also a :class:`ValueError`, so code that already guards against a bad value
    catches it without knowing this library exists. It is never an answer to a
    request: a webhook refused because of what it carries is a
    :class:`RejectWebhookError <xtr_webhook.exception.RejectWebhookError>`, while
    this is a mistake in the configuration to be fixed.
    """
