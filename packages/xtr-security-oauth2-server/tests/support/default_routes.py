"""The routes file the served fixture applications share: register everything at its default."""

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_http_kernel.routing.decorator import as_routes

if TYPE_CHECKING:
    from collections.abc import Mapping

    from fastapi import APIRouter, FastAPI


@as_routes
def oauth2_server(app: FastAPI, resources: Mapping[str, APIRouter]) -> None:
    """Serve every endpoint at its default path."""
    app.include_router(resources["oauth2_server"])
    app.include_router(resources["oauth2_server_well_known"])
