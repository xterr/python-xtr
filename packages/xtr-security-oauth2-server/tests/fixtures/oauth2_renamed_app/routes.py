"""A deployment moving the server's endpoints under /auth and renaming them."""

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_http_kernel.routing.decorator import as_routes

if TYPE_CHECKING:
    from collections.abc import Mapping

    from fastapi import APIRouter, FastAPI


@as_routes
def oauth2_server(app: FastAPI, resources: Mapping[str, APIRouter]) -> None:
    """Serve the protocol endpoints under /auth, every name under auth_."""
    server = resources["oauth2_server"]
    for route in server.routes:
        # The framework's base route type does not declare the name every kind carries.
        route.name = f"auth_{route.name}"  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType]  # ty: ignore[unresolved-attribute]
    app.include_router(server, prefix="/auth")
    app.include_router(resources["oauth2_server_well_known"])
