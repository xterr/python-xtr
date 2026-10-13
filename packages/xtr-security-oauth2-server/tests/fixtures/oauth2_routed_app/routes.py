"""A deployment moving the server's endpoints under /auth and leaving introspection out."""

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_http_kernel.routing.decorator import as_routes

if TYPE_CHECKING:
    from xtr_http_kernel.routing.loader.configurator import RoutingConfigurator


@as_routes
def oauth2_server(routes: RoutingConfigurator) -> None:
    _ = routes.import_("oauth2_server").prefix("/auth").exclude("oauth2_introspect")
    _ = routes.import_("oauth2_server_well_known")
