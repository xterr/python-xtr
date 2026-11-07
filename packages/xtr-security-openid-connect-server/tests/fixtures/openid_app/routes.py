"""The routes file of the deployment: the authorization server's endpoints at their defaults."""

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_http_kernel.routing.decorator import as_routes

if TYPE_CHECKING:
    from collections.abc import Mapping

    from fastapi import APIRouter, FastAPI

__all__ = ["oauth2_server"]


@as_routes
def oauth2_server(app: FastAPI, resources: Mapping[str, APIRouter]) -> None:
    """Serve every endpoint of the authorization server at its default path."""
    app.include_router(resources["oauth2_server"])
    app.include_router(resources["oauth2_server_well_known"])
