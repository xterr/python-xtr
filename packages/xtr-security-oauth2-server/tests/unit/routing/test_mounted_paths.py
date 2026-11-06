"""Where an application mounted each endpoint, read off its routes."""

from __future__ import annotations

from fastapi import APIRouter
from starlette.routing import Mount, Router

from xtr_security_oauth2_server import routing
from xtr_security_oauth2_server.routing import mounted_paths, paths_by_endpoint


async def _hello() -> None:
    """Answer nothing: only the function's identity is looked up."""


def test_paths_by_endpoint_is_public() -> None:
    assert "paths_by_endpoint" in routing.__all__
    assert paths_by_endpoint is mounted_paths.paths_by_endpoint


def test_paths_by_endpoint_ignores_routes_without_an_endpoint() -> None:
    router = APIRouter()
    router.add_api_route("/hello", _hello)

    paths = paths_by_endpoint([*router.routes, Mount("/static", Router())])

    assert paths == {_hello: "/hello"}
