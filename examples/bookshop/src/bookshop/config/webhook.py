"""Webhooks: which types the endpoint serves, and what each is verified against.

One route per sender. The type is the segment in the URL the endpoint serves —
``POST /webhook/{type}`` — so the subscriber is given that URL and nothing else
has to change when another sender is added.

The secret is read when the endpoint is built, not when the application boots,
so a placeholder keeps it out of this file and out of every container report.
"""

from __future__ import annotations

from xtr_dependency_injection import configure, env
from xtr_webhook.bundle import RouteConfig, WebhookConfig

__all__ = ["webhook"]


@configure
def webhook() -> WebhookConfig:
    """One type, verified with the bundle's own parser against ``WEBHOOK_SECRET``."""
    return WebhookConfig(
        routing={
            # A route with no parser uses the bundle's own, which verifies the
            # signature_format below. Name a class here for a sender that signs
            # its own way: RouteConfig(parser=AcmeRequestParser, secret=...).
            "payments": RouteConfig(secret=env("WEBHOOK_SECRET")),
        },
        # "legacy", "standard" or "transitional" — both ends must agree. Only
        # the Standard Webhooks signature covers the timestamp, so only it is
        # bounded by timestamp_tolerance.
        signature_format="legacy",
    )
