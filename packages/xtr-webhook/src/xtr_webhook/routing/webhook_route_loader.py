"""The route webhooks arrive at."""

from __future__ import annotations

from typing import final

from xtr_http_kernel.routing import Route, RouteCollection
from xtr_http_kernel.routing.decorator import as_route_loader

from xtr_webhook._endpoint_paths import ROUTE_NAME, WEBHOOK_PATH

from ._endpoints import webhook

__all__ = ["WebhookRouteLoader"]


@final
@as_route_loader("webhook")
class WebhookRouteLoader:
    """The one endpoint every incoming webhook arrives at, ``POST /webhook/{type}``.

    An application imports it as ``"webhook"`` and may move it under a prefix
    in a routes file. Wherever it lands, the URL a sender is given has to be the
    path served, so build it from the route's name rather than writing it out.
    """

    def load_routes(self) -> RouteCollection:
        """Return the endpoint at its default path and name."""
        routes = RouteCollection()
        routes.add(ROUTE_NAME, Route(WEBHOOK_PATH, webhook, methods=("POST",)))
        return routes
