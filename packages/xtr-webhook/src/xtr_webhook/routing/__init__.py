"""The endpoint webhooks arrive at, contributed to the application's route table.

- :class:`WebhookRouteLoader` — resource ``"webhook"``: ``POST /webhook/{type}``, movable
  under a prefix.
"""

from __future__ import annotations

from .webhook_route_loader import WebhookRouteLoader

__all__ = ["WebhookRouteLoader"]
