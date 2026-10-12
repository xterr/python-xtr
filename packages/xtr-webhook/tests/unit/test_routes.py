"""The router carries the one endpoint every incoming webhook arrives at."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.routing import APIRoute

from xtr_webhook._endpoint_paths import ROUTE_NAME, WEBHOOK_PATH
from xtr_webhook.routes import routes


def _declared(prefix: str = "") -> list[APIRoute]:
    """Return every route the router carries."""
    return [route for route in routes(prefix).routes if isinstance(route, APIRoute)]


def test_it_returns_a_router_an_application_can_include() -> None:
    assert isinstance(routes(), APIRouter)


def test_it_declares_the_one_endpoint_and_no_other() -> None:
    assert len(_declared()) == 1


def test_a_webhook_is_received_by_posting_it() -> None:
    assert _declared()[0].methods == {"POST"}


def test_the_type_a_webhook_is_for_is_a_segment_of_the_path() -> None:
    assert _declared()[0].path == "/webhook/{type}"
    assert WEBHOOK_PATH == "/webhook/{type}"


def test_the_route_carries_the_name_an_application_builds_a_url_by() -> None:
    assert _declared()[0].name == ROUTE_NAME
    assert ROUTE_NAME == "webhook"


def test_a_prefix_moves_the_whole_endpoint_under_it() -> None:
    assert _declared(prefix="/hooks")[0].path == "/hooks/webhook/{type}"


def test_a_second_router_is_a_separate_object() -> None:
    # An application including the routes twice — two mounts, a test building
    # one per case — must not share route objects.
    assert routes() is not routes()
