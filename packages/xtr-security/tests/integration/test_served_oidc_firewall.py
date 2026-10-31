"""The security bundle wires an OIDC firewall over a real served application.

Drives the served OIDC fixture through ``httpx.ASGITransport`` inside the app's
lifespan — never ``TestClient`` — so ``setup(app, kernel)`` builds and boots the
kernel per life. A token minted against the pinned JWKS authenticates; a missing
or bad one is challenged. No network: the keys are pinned in the configuration.
"""

from __future__ import annotations

import base64
from typing import TYPE_CHECKING

import httpx
import pytest

from tests.fixtures.oidc_app.app import app
from tests.fixtures.oidc_app.keys import mint

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

pytestmark = pytest.mark.anyio

#: Protected headers joserfc cannot judge: a ``crit`` that is no list of names,
#: and a header that is no JSON object at all.
HOSTILE_HEADERS = (
    b'{"alg":"RS256","crit":5}',
    b'{"alg":"RS256","crit":[["a"]]}',
    b'["alg"]',
    b'"alg"',
)


def _under_header(header: bytes) -> str:
    """Return a compact token carrying ``header``, an empty payload and a forged signature."""
    return ".".join(
        base64.urlsafe_b64encode(part).rstrip(b"=").decode() for part in (header, b"{}", b"x" * 32)
    )


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


@pytest.mark.parametrize("header", HOSTILE_HEADERS)
async def test_a_token_whose_header_joserfc_cannot_judge_is_an_invalid_token(
    client: httpx.AsyncClient,
    header: bytes,
) -> None:
    response = await client.get(
        "/api/me",
        headers={"authorization": f"Bearer {_under_header(header)}"},
    )

    assert response.status_code == 401
    assert response.json() == {"error": "invalid_token"}
