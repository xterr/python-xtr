"""The security bundle wires an OIDC firewall over a real served application.

Drives the served OIDC fixture through ``httpx.ASGITransport`` inside the app's
lifespan — never ``TestClient`` — so ``setup(app, kernel)`` builds and boots the
kernel per life. A token minted against the pinned JWKS authenticates; a missing
or bad one is challenged. No network: the keys are pinned in the configuration.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx
import pytest

from tests.fixtures.oidc_app.app import app
from tests.fixtures.oidc_app.keys import mint

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

pytestmark = pytest.mark.anyio


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    """Serve the OIDC fixture app inside its lifespan."""
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as opened:
            yield opened


async def test_a_valid_oidc_token_is_authenticated(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/me", headers={"authorization": f"Bearer {mint()}"})

    assert response.status_code == 200
    assert response.json() == {"user": "alice"}


async def test_no_token_is_challenged(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/me")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == 'Bearer realm="api"'


async def test_a_bad_token_is_an_invalid_token(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/me", headers={"authorization": "Bearer not-a-jwt"})

    assert response.status_code == 401
    assert response.json() == {"error": "invalid_token"}
    assert 'error="invalid_token"' in response.headers["www-authenticate"]


async def test_a_token_for_another_audience_is_rejected(client: httpx.AsyncClient) -> None:
    token = mint(audience="other-api")

    response = await client.get("/api/me", headers={"authorization": f"Bearer {token}"})

    assert response.status_code == 401
    assert response.json() == {"error": "invalid_token"}
