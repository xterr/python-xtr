"""The factory seam a third-party bundle extends the security family through.

A fake bundle prepends an authenticator factory (key ``fake_oauth2``) and a
token-handler factory onto the security config; an application configures a
firewall with the fake authenticator, requests authenticate through it, its
scope gates a route, and ``debug:firewall`` lists the firewall. No xtr-security
code knows the fake — the seam is proven open (S-1, S-2).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx
import pytest

from tests.fixtures.seam_app.app import app, kernel

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

pytestmark = pytest.mark.anyio


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    """Serve the seam fixture app inside its lifespan."""
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as opened:
            yield opened


async def test_the_fake_authenticator_authenticates_a_request(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/ping", headers={"authorization": "Bearer granted"})

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_the_fake_authenticator_challenges_without_a_token(
    client: httpx.AsyncClient,
) -> None:
    response = await client.get("/api/ping")

    assert response.status_code == 401
    assert 'realm="fake"' in response.headers["www-authenticate"]


async def test_the_fake_handler_rejects_an_unknown_token(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/ping", headers={"authorization": "Bearer denied"})

    assert response.status_code == 401
    assert response.json() == {"error": "invalid_token"}


async def test_the_fakes_scope_gates_a_route(client: httpx.AsyncClient) -> None:
    granted = await client.get("/api/scoped", headers={"authorization": "Bearer granted"})

    assert granted.status_code == 200


async def test_debug_firewall_lists_the_seam_firewall() -> None:
    from xtr_console import Application, CommandTester
    from xtr_dependency_injection.testing import boot_for_test

    async with await boot_for_test(kernel) as booted:
        application = await booted.container.get(Application)
        tester = CommandTester(application, "debug:firewall")
        exit_code = await tester.execute()

    assert exit_code == 0
    assert "api" in tester.display
