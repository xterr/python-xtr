"""A deployment's routes file moving the provider's userinfo endpoint under /oidc.

The configuration document stays at the root: a client finds it at a fixed
path under the issuer, wherever the endpoints it names were moved.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_http_kernel.routing.decorator import as_routes

if TYPE_CHECKING:
    from collections.abc import Mapping

    from fastapi import APIRouter, FastAPI

__all__ = ["oauth2_server", "openid_connect_server"]


@as_routes
def oauth2_server(app: FastAPI, resources: Mapping[str, APIRouter]) -> None:
    """Serve every endpoint of the authorization server at its default path."""
    app.include_router(resources["oauth2_server"])
    app.include_router(resources["oauth2_server_well_known"])


@as_routes
def openid_connect_server(app: FastAPI, resources: Mapping[str, APIRouter]) -> None:
    """Serve the userinfo endpoint under /oidc, and the configuration document at the root."""
    app.include_router(resources["openid_connect_server"], prefix="/oidc")
    app.include_router(resources["openid_connect_server_well_known"])
