"""Where this application receives webhooks: ``POST /webhook/{type}`` by default.

This file is what registers the endpoint: routing is never imported
automatically, and deleting it stops the application receiving webhooks. Give
each sender the URL built from the route's name, ``"webhook"``, rather than
writing the path out: a sender that was told a URL keeps sending to it long
after the deploy that moved it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_http_kernel.routing.decorator import as_routes

if TYPE_CHECKING:
    from collections.abc import Mapping

    from fastapi import APIRouter, FastAPI

__all__ = ["webhook"]


@as_routes
def webhook(app: FastAPI, resources: Mapping[str, APIRouter]) -> None:
    """Serve the endpoint at its default path."""
    app.include_router(resources["webhook"])
    # To keep everything a stranger may call under one path, include it with a
    # prefix instead: app.include_router(resources["webhook"], prefix="/hooks")
