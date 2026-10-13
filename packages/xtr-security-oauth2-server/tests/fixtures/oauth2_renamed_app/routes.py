"""A deployment moving the server's endpoints under /auth and renaming them."""

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_http_kernel.routing.decorator import as_routes

if TYPE_CHECKING:
    from xtr_http_kernel.routing.loader.configurator import RoutingConfigurator


@as_routes
def oauth2_server(routes: RoutingConfigurator) -> None:
    _ = routes.import_("oauth2_server").prefix("/auth").name_prefix("auth_")
