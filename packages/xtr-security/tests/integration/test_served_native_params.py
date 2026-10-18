"""The framework's own security params, resolved beside the firewall the bundle runs.

The firewall — a subscriber over the kernel lifecycle's events — authenticates
every request the configuration's firewall claims, before routing; the routes
of the native-params fixture then resolve their parameters the way the
framework documents it. A served test proves the two coexist: the firewall
challenges first, and the native params read the same request after it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx
import pytest

from tests.fixtures.native_app.app import app

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

pytestmark = pytest.mark.anyio


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    """Serve the native-params fixture app inside its lifespan."""
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as opened:
            yield opened


async def test_a_public_routes_bearer_param_resolves_beside_the_firewall(
    client: httpx.AsyncClient,
) -> None:
    anonymous = await client.get("/api/open/bearer")
    authenticated = await client.get("/api/open/bearer", headers={"authorization": "Bearer good"})

    assert anonymous.status_code == 200
    assert anonymous.json() == {"credential": None}
    assert authenticated.status_code == 200
    assert authenticated.json() == {"credential": "good"}


async def test_a_secured_route_challenges_before_its_native_params_resolve(
    client: httpx.AsyncClient,
) -> None:
    response = await client.get("/api/scopes")

    assert response.status_code == 401


async def test_the_frameworks_scopes_and_bearer_params_resolve_after_the_firewall(
    client: httpx.AsyncClient,
) -> None:
    response = await client.get(
        "/api/scopes",
        headers={"authorization": "Bearer good"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "scopes": ["books:read"],
        "credential": "good",
        "user": "alice",
    }


async def test_an_api_key_header_and_a_plain_dependency_resolve_beside_the_firewall(
    client: httpx.AsyncClient,
) -> None:
    without = await client.get("/api/key", headers={"authorization": "Bearer good"})
    with_key = await client.get(
        "/api/key", headers={"authorization": "Bearer good", "x-api-key": "s3cret"}
    )

    assert without.status_code == 200
    assert without.json() == {"key": None, "pong": "pong"}
    assert with_key.status_code == 200
    assert with_key.json() == {"key": "s3cret", "pong": "pong"}
