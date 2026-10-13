"""The one endpoint every incoming webhook arrives at, contributed to the route table."""

from __future__ import annotations

from xtr_http_kernel.routing.decorator import RouteLoaderMarker, route_loaders_of

from xtr_webhook._endpoint_paths import ROUTE_NAME, WEBHOOK_PATH
from xtr_webhook.routing import WebhookRouteLoader


def test_it_is_imported_as_webhook_and_may_be_moved() -> None:
    assert route_loaders_of(WebhookRouteLoader) == (RouteLoaderMarker("webhook", prefixable=True),)


def test_it_contributes_the_one_endpoint_posted_to_under_its_name() -> None:
    routes = {
        name: (route.path, route.methods) for name, route in WebhookRouteLoader().load_routes()
    }

    assert routes == {ROUTE_NAME: (WEBHOOK_PATH, ("POST",))}
    assert (ROUTE_NAME, WEBHOOK_PATH) == ("webhook", "/webhook/{type}")
