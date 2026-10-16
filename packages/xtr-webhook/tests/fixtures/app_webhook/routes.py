"""The application's routes file: what registers the webhook endpoint."""

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_http_kernel.routing.decorator import as_routes

if TYPE_CHECKING:
    from collections.abc import Mapping

    from fastapi import APIRouter, FastAPI


@as_routes
def webhook(app: FastAPI, resources: Mapping[str, APIRouter]) -> None:
    """Serve the endpoint at its default path."""
    app.include_router(resources["webhook"])
