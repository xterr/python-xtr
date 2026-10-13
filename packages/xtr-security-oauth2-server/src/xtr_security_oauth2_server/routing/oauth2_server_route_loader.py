"""The routes a client and a resource owner's browser reach this server at."""

from __future__ import annotations

from typing import final

from xtr_http_kernel.routing import Route, RouteCollection
from xtr_http_kernel.routing.decorator import as_route_loader

from xtr_security_oauth2_server._endpoint_paths import (
    AUTHORIZE_PATH,
    DEVICE_CODE_PATH,
    INTROSPECT_PATH,
    REVOKE_PATH,
    ROUTE_NAMES,
    TOKEN_PATH,
)

from ._endpoints import authorize, device_code, introspect, revoke, token

__all__ = ["OAuth2ServerRouteLoader"]


@final
@as_route_loader("oauth2_server")
class OAuth2ServerRouteLoader:
    """The authorization, token, device-code, revocation and introspection endpoints.

    An application imports them as ``"oauth2_server"`` and may move them under
    a prefix: the discovery document names wherever they end up. Every one is
    contributed; an endpoint a deployment turned off answers 404, and an
    application that wants it gone leaves it out in its routes file.
    """

    def load_routes(self) -> RouteCollection:
        """Return the five endpoints at their default paths and names."""
        routes = RouteCollection()
        routes.add(
            ROUTE_NAMES[AUTHORIZE_PATH],
            Route(AUTHORIZE_PATH, authorize, methods=("GET", "POST")),
        )
        routes.add(ROUTE_NAMES[TOKEN_PATH], Route(TOKEN_PATH, token, methods=("POST",)))
        routes.add(
            ROUTE_NAMES[DEVICE_CODE_PATH],
            Route(DEVICE_CODE_PATH, device_code, methods=("POST",)),
        )
        routes.add(ROUTE_NAMES[REVOKE_PATH], Route(REVOKE_PATH, revoke, methods=("POST",)))
        routes.add(
            ROUTE_NAMES[INTROSPECT_PATH],
            Route(INTROSPECT_PATH, introspect, methods=("POST",)),
        )
        return routes
