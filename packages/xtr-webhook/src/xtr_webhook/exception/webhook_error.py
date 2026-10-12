"""The error every other error of this package derives from."""

from __future__ import annotations

__all__ = ["WebhookError"]


class WebhookError(Exception):
    """Something a webhook could not be — catch this to catch them all."""
