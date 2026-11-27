"""The provider's endpoints, contributed under the names a URL is built by."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.routing import APIRoute

from xtr_security_openid_connect_server.routing import openid_connect_server_routes


def test_the_userinfo_endpoint_answers_each_method_on_a_route_of_its_own() -> None:
    router = APIRouter()
    openid_connect_server_routes(router)
    routes = [route for route in router.routes if isinstance(route, APIRoute)]

    assert {(route.name, route.path, tuple(route.methods or ())) for route in routes} == {
        ("openid_connect_server_userinfo", "/userinfo", ("GET",)),
        ("openid_connect_server_userinfo_post", "/userinfo", ("POST",)),
    }
    assert len({route.unique_id for route in routes}) == len(routes)
