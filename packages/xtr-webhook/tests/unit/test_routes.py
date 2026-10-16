"""The route webhooks arrive at, contributed as the webhook resource."""

from __future__ import annotations

from typing import cast

from fastapi import APIRouter
from fastapi.routing import APIRoute
from xtr_http_kernel.routing.decorator import route_resources_of

from xtr_webhook._endpoint_paths import ROUTE_NAME, WEBHOOK_PATH
from xtr_webhook.routes import webhook_routes


def test_it_is_imported_as_webhook() -> None:
    assert route_resources_of(webhook_routes) == ("webhook",)


def test_it_registers_the_one_endpoint_posted_to_under_its_name() -> None:
    router = APIRouter()
    webhook_routes(router)

    (registered,) = (route for route in router.routes if isinstance(route, APIRoute))
    assert (registered.name, registered.path, registered.methods) == (
        ROUTE_NAME,
        WEBHOOK_PATH,
        {"POST"},
    )
    assert (ROUTE_NAME, WEBHOOK_PATH) == ("webhook", "/webhook/{type}")
    assert cast("object", registered.endpoint) is not None
