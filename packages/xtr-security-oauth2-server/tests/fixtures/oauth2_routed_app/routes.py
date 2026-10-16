"""A deployment moving the server's endpoints under /auth and leaving introspection out."""

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_http_kernel.routing.decorator import as_routes

if TYPE_CHECKING:
    from collections.abc import Mapping

    from fastapi import APIRouter, FastAPI


@as_routes
def oauth2_server(app: FastAPI, resources: Mapping[str, APIRouter]) -> None:
    """Serve the protocol endpoints under /auth, minus introspection, and the documents."""
    server = resources["oauth2_server"]
    server.routes = [
        route for route in server.routes if getattr(route, "name", None) != "oauth2_introspect"
    ]
    app.include_router(server, prefix="/auth")
    app.include_router(resources["oauth2_server_well_known"])
