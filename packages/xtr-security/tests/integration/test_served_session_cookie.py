"""The cookie a stateful firewall's session travels in, over a real served application.

The session cookie fixture names its own cookie, ``sid``, ``Secure``. The login
rotates the session and stages that cookie under the new ID, the next request
is reattached by it, and the logout re-issues it under a fresh ID with the same
attributes, so the browser replaces the cookie it holds rather than keeping a
second one. The forgery-token fixture configures no cookie and keeps the
session's default.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import httpx
import pytest

from tests.fixtures.csrf_app.app import app as default_cookie_app
from tests.fixtures.session_cookie_app.app import app

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from fastapi import FastAPI

pytestmark = pytest.mark.anyio

#: The ``Set-Cookie`` the fixture's configuration stages, its ID left open.
CONFIGURED = re.compile(r"sid=([0-9a-f]{48}); path=/; secure; httponly; samesite=lax")

#: The ``Set-Cookie`` a firewall configuring no cookie stages, its ID left open.
DEFAULT = re.compile(r"xtr_session=([0-9a-f]{48}); path=/; httponly; samesite=lax")

_LOGIN = {"_username": "alice", "_password": "secret"}


async def _serving(served: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    """Serve ``served`` inside its lifespan, over HTTPS so a ``Secure`` cookie comes back."""
    async with served.router.lifespan_context(served):
        transport = httpx.ASGITransport(served, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="https://test") as opened:
            yield opened


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    """Serve the session cookie fixture."""
    async for opened in _serving(app):
        yield opened


@pytest.fixture
async def default_client() -> AsyncIterator[httpx.AsyncClient]:
    """Serve the fixture that configures no cookie."""
    async for opened in _serving(default_cookie_app):
        yield opened


def _session_id(response: httpx.Response, shape: re.Pattern[str]) -> str:
    """Return the session ID the one ``Set-Cookie`` of ``response`` carries, in ``shape``."""
    (staged,) = response.headers.get_list("set-cookie")
    matched = shape.fullmatch(staged)
    assert matched is not None, f"{staged!r} is not the configured cookie"
    return matched.group(1)


async def test_a_login_stages_the_configured_cookie(client: httpx.AsyncClient) -> None:
    response = await client.post("/login_check", params=_LOGIN)

    assert response.status_code == 302
    _ = _session_id(response, CONFIGURED)


async def test_the_next_request_is_reattached_by_the_configured_cookie(
    client: httpx.AsyncClient,
) -> None:
    _ = await client.post("/login_check", params=_LOGIN)

    home = await client.get("/")

    assert home.status_code == 200
    assert "alice" in home.text


async def test_the_logins_rotation_stages_the_configured_cookie_under_a_new_id(
    client: httpx.AsyncClient,
) -> None:
    first = await client.get("/login_check", params={**_LOGIN, "_password": "wrong"})
    before = _session_id(first, CONFIGURED)

    logged_in = await client.post("/login_check", params=_LOGIN)

    assert _session_id(logged_in, CONFIGURED) != before


async def test_a_logout_reissues_the_configured_cookie_with_the_same_attributes(
    client: httpx.AsyncClient,
) -> None:
    logged_in = _session_id(await client.post("/login_check", params=_LOGIN), CONFIGURED)

    logged_out = await client.post("/logout")

    assert logged_out.status_code == 302
    assert _session_id(logged_out, CONFIGURED) != logged_in
    assert (await client.get("/")).status_code == 302


async def test_a_firewall_configuring_no_cookie_stages_the_sessions_default(
    default_client: httpx.AsyncClient,
) -> None:
    response = await default_client.get("/login")

    _ = _session_id(response, DEFAULT)
