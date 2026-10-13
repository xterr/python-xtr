"""The server's endpoints, contributed under the names a URL is built by."""

from __future__ import annotations

from xtr_http_kernel.routing.decorator import RouteLoaderMarker, route_loaders_of

from xtr_security_oauth2_server.routing import OAuth2ServerRouteLoader


def _routes() -> dict[str, tuple[str, tuple[str, ...]]]:
    return {
        name: (route.path, route.methods) for name, route in OAuth2ServerRouteLoader().load_routes()
    }


def test_it_is_imported_as_oauth2_server_and_may_be_moved() -> None:
    assert route_loaders_of(OAuth2ServerRouteLoader) == (
        RouteLoaderMarker("oauth2_server", prefixable=True),
    )


def test_every_endpoint_is_contributed_under_the_name_a_url_is_built_by() -> None:
    assert _routes() == {
        "oauth2_authorize": ("/authorize", ("GET", "POST")),
        "oauth2_token": ("/token", ("POST",)),
        "oauth2_device_code": ("/device-code", ("POST",)),
        "oauth2_revoke": ("/revoke", ("POST",)),
        "oauth2_introspect": ("/introspect", ("POST",)),
    }


def test_the_authorization_endpoint_also_answers_the_consent_form_posting_back() -> None:
    assert "POST" in _routes()["oauth2_authorize"][1]
