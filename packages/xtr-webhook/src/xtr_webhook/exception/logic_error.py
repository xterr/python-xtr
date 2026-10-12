"""This library was used in a way that cannot work."""

from __future__ import annotations

from .webhook_error import WebhookError

__all__ = ["LogicError"]


class LogicError(WebhookError, RuntimeError):
    """This library was used in a way that cannot work, whatever the request carries.

    A parser asked for a header its format never sends, a signer without a secret
    to sign with: each is a mistake in the code, so retrying it changes nothing.
    """
