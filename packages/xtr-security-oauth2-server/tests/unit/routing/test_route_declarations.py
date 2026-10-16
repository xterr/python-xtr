"""The server's endpoints, contributed under the names a URL is built by."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter
from fastapi.routing import APIRoute
from xtr_http_kernel.routing.decorator import route_resources_of

from xtr_security_oauth2_server.routing import oauth2_server_routes, well_known_routes

if TYPE_CHECKING:
    from collections.abc import Callable


def _mounted(fill: Callable[[APIRouter], None]) -> dict[str, tuple[str, tuple[str, ...]]]:
    router = APIRouter()
    fill(router)
    return {
        route.name: (route.path, tuple(sorted(route.methods or ())))
        for route in router.routes
        if isinstance(route, APIRoute)
    }


def test_it_is_imported_as_oauth2_server() -> None:
    assert route_resources_of(oauth2_server_routes) == ("oauth2_server",)


def test_every_protocol_endpoint_is_contributed_under_the_name_a_url_is_built_by() -> None:
    assert _mounted(oauth2_server_routes) == {
        "oauth2_authorize": ("/authorize", ("GET", "POST")),
        "oauth2_token": ("/token", ("POST",)),
        "oauth2_device_code": ("/device-code", ("POST",)),
        "oauth2_revoke": ("/revoke", ("POST",)),
        "oauth2_introspect": ("/introspect", ("POST",)),
    }


def test_the_authorization_endpoint_also_answers_the_consent_form_posting_back() -> None:
    assert "POST" in _mounted(oauth2_server_routes)["oauth2_authorize"][1]


def test_the_well_known_documents_live_where_the_standard_fixes_them() -> None:
    assert route_resources_of(well_known_routes) == ("oauth2_server_well_known",)
    assert _mounted(well_known_routes) == {
        "oauth2_metadata": ("/.well-known/oauth-authorization-server", ("GET",)),
        "oauth2_jwks": ("/.well-known/jwks.json", ("GET",)),
    }
