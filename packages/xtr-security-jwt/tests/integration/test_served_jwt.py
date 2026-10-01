"""The JWT bundle over a real served FastAPI application.

Drives the fixture app through ``httpx.ASGITransport`` inside the app's own
lifespan — never ``TestClient`` — so ``setup(app, kernel)`` builds and boots the
kernel per life. Covers the whole request surface a self-issued token draws:
the not-found, invalid, expired and tampered challenges, a good token, the role
gate, the events the firewall dispatches, and that the token manager is
injectable.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import httpx
import pytest

from tests.fixtures.jwt_app import listeners
from tests.fixtures.jwt_app.app import app
from tests.fixtures.jwt_app.keys import PRIVATE_PEM
from tests.support.tokens import mint_token

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

pytestmark = pytest.mark.anyio


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    """Serve the fixture app inside its lifespan, cleared of recorded events."""
    listeners.EVENTS.clear()
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as opened:
            yield opened


async def _bearer(
    identifier: str, roles: tuple[str, ...] = ("ROLE_USER",), **kwargs: object
) -> str:
    ttl = kwargs.get("ttl", 3600)
    when = kwargs.get("when")
    return await mint_token(
        PRIVATE_PEM,
        identifier,
        roles,
        ttl=ttl if isinstance(ttl, int) else 3600,
        when=when if isinstance(when, str) else None,
    )


async def test_no_token_is_a_not_found_challenge(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/me")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json() == {"code": 401, "message": "JWT Token not found"}
    assert listeners.EVENTS[-1].endswith("JwtNotFoundEvent")


async def test_a_good_token_is_authenticated(client: httpx.AsyncClient) -> None:
    token = await _bearer("ada", ("ROLE_USER",))

    response = await client.get("/api/me", headers={"authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json() == {"user": "ada", "roles": ["ROLE_USER"]}
    assert listeners.EVENTS[-1].endswith("JwtAuthenticatedEvent")


async def test_a_tampered_token_is_invalid(client: httpx.AsyncClient) -> None:
    token = await _bearer("ada")

    response = await client.get(
        "/api/me",
        headers={"authorization": f"Bearer {token[:-3]}aaa"},
    )

    assert response.status_code == 401
    assert response.json() == {"code": 401, "message": "Invalid JWT Token"}
    assert listeners.EVENTS[-1].endswith("JwtInvalidEvent")


async def test_a_structurally_broken_token_is_invalid(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/me", headers={"authorization": "Bearer nonsense"})

    assert response.status_code == 401
    assert response.json()["message"] == "Invalid JWT Token"


async def test_an_expired_token_is_expired(client: httpx.AsyncClient) -> None:
    token = await _bearer("ada", ("ROLE_USER",), ttl=50, when="2020-01-01 00:00:00")

    response = await client.get("/api/me", headers={"authorization": f"Bearer {token}"})

    assert response.status_code == 401
    assert response.json() == {"code": 401, "message": "Expired JWT Token"}
    assert listeners.EVENTS[-1].endswith("JwtExpiredEvent")


async def test_a_token_signed_by_another_key_is_invalid(client: httpx.AsyncClient) -> None:
    from tests.support.keys import RSA_PRIVATE_PEM  # noqa: PLC0415

    token = await mint_token(RSA_PRIVATE_PEM, "ada")

    response = await client.get("/api/me", headers={"authorization": f"Bearer {token}"})

    assert response.status_code == 401
    assert response.json()["message"] == "Invalid JWT Token"


async def test_the_none_algorithm_is_refused(client: httpx.AsyncClient) -> None:
    unsigned = "eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJ1c2VybmFtZSI6ImFkYSJ9."

    response = await client.get("/api/me", headers={"authorization": f"Bearer {unsigned}"})

    assert response.status_code == 401
    assert response.json()["message"] == "Invalid JWT Token"


async def test_a_missing_id_claim_is_an_invalid_payload(client: httpx.AsyncClient) -> None:
    token = await mint_token(PRIVATE_PEM, "ada", user_id_claim="sub")

    response = await client.get("/api/me", headers={"authorization": f"Bearer {token}"})

    assert response.status_code == 401
    assert "username" in response.json()["message"]


async def test_a_held_role_is_granted(client: httpx.AsyncClient) -> None:
    token = await _bearer("root", ("ROLE_USER", "ROLE_ADMIN"))

    response = await client.get(
        "/api/admin/panel",
        headers={"authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "admin"}


async def test_a_missing_role_is_forbidden(client: httpx.AsyncClient) -> None:
    token = await _bearer("ada", ("ROLE_USER",))

    response = await client.get(
        "/api/admin/panel",
        headers={"authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


async def test_the_token_manager_is_injectable(client: httpx.AsyncClient) -> None:
    response = await client.get("/manager")

    assert response.status_code == 200
    assert response.json() == {"manager": "JwtManager"}


async def test_the_openapi_schema_names_a_bearer_scheme(client: httpx.AsyncClient) -> None:
    response = await client.get("/openapi.json")

    document = cast("dict[str, object]", response.json())
    components = cast("dict[str, object]", document["components"])
    schemes = cast("dict[str, dict[str, object]]", components["securitySchemes"])
    assert any(scheme.get("scheme") == "bearer" for scheme in schemes.values())
