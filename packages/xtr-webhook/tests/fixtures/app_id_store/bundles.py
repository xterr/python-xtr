"""The application's root bundles: only WebhookBundle, which brings the rest."""

from __future__ import annotations

from xtr_webhook.bundle import WebhookBundle

BUNDLES = {WebhookBundle: {"all": True}}
