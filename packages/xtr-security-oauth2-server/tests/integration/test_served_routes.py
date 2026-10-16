"""The server's endpoints as a deployment's routes file arranges them."""

from __future__ import annotations

import pytest

from tests.support.served import json_of, oauth2_kernel, served_application, serving
from tests.support.signing import ISSUER

pytestmark = pytest.mark.anyio

_ROUTED = "tests.fixtures.oauth2_routed_app"


async def test_with_the_default_routes_file_every_endpoint_is_served_at_its_default_path() -> None:
    app = served_application(oauth2_kernel())

    async with serving(app) as client:
        token = await client.post("/token", data={"grant_type": "client_credentials"})

    # Reached the endpoint: refused for naming no client, not by the router.
    assert token.status_code in {400, 401}
    assert app.url_path_for("oauth2_introspect") == "/introspect"


async def test_a_moved_endpoint_is_served_and_published_where_it_now_is() -> None:
    app = served_application(oauth2_kernel(_ROUTED, routes_module=None))

    async with serving(app) as client:
        old = await client.post("/token", data={"grant_type": "client_credentials"})
        moved = await client.post("/auth/token", data={"grant_type": "client_credentials"})
        document = json_of(await client.get("/.well-known/oauth-authorization-server"))

    assert old.status_code == 404
    assert moved.status_code in {400, 401}
    assert document["token_endpoint"] == f"{ISSUER}/auth/token"
    assert document["jwks_uri"] == f"{ISSUER}/.well-known/jwks.json"


async def test_an_endpoint_left_out_is_neither_served_nor_published() -> None:
    app = served_application(oauth2_kernel(_ROUTED, routes_module=None))

    async with serving(app) as client:
        introspected = await client.post("/auth/introspect", data={"token": "x"})
        document = json_of(await client.get("/.well-known/oauth-authorization-server"))

    assert introspected.status_code == 404
    assert "introspection_endpoint" not in document


async def test_renamed_endpoints_are_still_published_where_they_are() -> None:
    app = served_application(oauth2_kernel("tests.fixtures.oauth2_renamed_app", routes_module=None))

    async with serving(app) as client:
        document = json_of(await client.get("/.well-known/oauth-authorization-server"))

    assert app.url_path_for("auth_oauth2_token") == "/auth/token"
    assert document["token_endpoint"] == f"{ISSUER}/auth/token"
    assert document["introspection_endpoint"] == f"{ISSUER}/auth/introspect"
