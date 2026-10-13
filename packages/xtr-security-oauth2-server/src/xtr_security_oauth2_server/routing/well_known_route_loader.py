"""The documents a standard places under ``/.well-known/``."""

from __future__ import annotations

from typing import final

from xtr_http_kernel.routing import Route, RouteCollection
from xtr_http_kernel.routing.decorator import as_route_loader

from xtr_security_oauth2_server._endpoint_paths import JWKS_PATH, METADATA_PATH, ROUTE_NAMES

from ._endpoints import jwks, metadata

__all__ = ["WellKnownRouteLoader"]


@final
@as_route_loader("oauth2_server_well_known", prefixable=False)
class WellKnownRouteLoader:
    """This server's description and the key set its tokens are verified against.

    RFC 8414 fixes where the description lives relative to the issuer, so these
    routes cannot be moved under a prefix; a routes file may still leave them
    out, or skip them.
    """

    def load_routes(self) -> RouteCollection:
        """Return the description and the key set at their fixed paths."""
        routes = RouteCollection()
        routes.add(ROUTE_NAMES[METADATA_PATH], Route(METADATA_PATH, metadata, methods=("GET",)))
        routes.add(ROUTE_NAMES[JWKS_PATH], Route(JWKS_PATH, jwks, methods=("GET",)))
        return routes
