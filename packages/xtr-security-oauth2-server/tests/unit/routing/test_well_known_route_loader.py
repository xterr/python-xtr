"""The description and the key set, contributed where RFC 8414 puts them."""

from __future__ import annotations

from xtr_http_kernel.routing.decorator import RouteLoaderMarker, route_loaders_of

from xtr_security_oauth2_server.routing import WellKnownRouteLoader


def test_it_is_imported_as_oauth2_server_well_known_and_may_not_be_moved() -> None:
    assert route_loaders_of(WellKnownRouteLoader) == (
        RouteLoaderMarker("oauth2_server_well_known", prefixable=False),
    )


def test_the_description_and_the_key_set_live_where_the_standard_fixes_them() -> None:
    routes = {
        name: (route.path, route.methods) for name, route in WellKnownRouteLoader().load_routes()
    }

    assert routes == {
        "oauth2_metadata": ("/.well-known/oauth-authorization-server", ("GET",)),
        "oauth2_jwks": ("/.well-known/jwks.json", ("GET",)),
    }
