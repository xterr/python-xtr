"""Concurrent first logins of a freshly booted application each go through every check.

The firewall's dispatcher builds its service listeners — the credentials
check among them — the first time a login reaches them; a login held ahead of
them meanwhile must still meet each one.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import httpx
import pytest

from tests.fixtures.firewall_race_app import listeners
from tests.fixtures.firewall_race_app.app import app

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

pytestmark = pytest.mark.anyio


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    """Serve the fixture app inside a lifespan of its own, so no listener is built yet."""
    for name in ("ada", "bob"):
        listeners.ARRIVED[name] = asyncio.Event()
        listeners.RELEASE[name] = asyncio.Event()
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as opened:
            yield opened
    listeners.ARRIVED.clear()
    listeners.RELEASE.clear()


async def test_concurrent_cold_requests_both_pass_the_firewall(client: httpx.AsyncClient) -> None:
    first = asyncio.create_task(
        client.post("/api/login", json={"username": "ada", "password": "secret"})
    )
    second = asyncio.create_task(
        client.post("/api/login", json={"username": "bob", "password": "secret"})
    )
    _ = await listeners.ARRIVED["ada"].wait()
    _ = await listeners.ARRIVED["bob"].wait()

    listeners.RELEASE["ada"].set()
    first_response = await first
    listeners.RELEASE["bob"].set()
    second_response = await second

    assert first_response.json() == {"user": "ada"}
    assert second_response.json() == {"user": "bob"}
