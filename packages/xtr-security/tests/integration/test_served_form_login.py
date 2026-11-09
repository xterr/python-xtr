"""The form login, the JSON login and the posted switch, over a served app.

Drives the form-login fixture through ``httpx.ASGITransport`` inside the app's
own lifespan, every submission posted the way a browser or a client posts it:
the form login's fields, the switch's username and the page's own form ride
the request's body as a form, and the JSON login's document rides it as JSON.
The chain reads each body before it asks for the fields in it, and the route
behind the firewall still reads the body it was posted.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx
import pytest

from tests.fixtures.form_login_app.app import app

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

pytestmark = pytest.mark.anyio


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    """Serve the fixture app inside its lifespan."""
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as opened:
            yield opened


async def _login(client: httpx.AsyncClient, password: str) -> httpx.Response:
    """Post the login form as ``ada`` with ``password``, the way a browser submits it."""
    return await client.post("/login_check", data={"_username": "ada", "_password": password})


async def test_a_form_login_posted_as_its_body_redirects_to_the_target(
    client: httpx.AsyncClient,
) -> None:
    response = await client.post(
        "/login_check",
        data={"_username": "ada", "_password": "secret", "_target_path": "/account"},
    )

    assert response.status_code == 302
    assert response.headers["location"] == "/account"


async def test_a_wrong_password_returns_to_the_login_page(client: httpx.AsyncClient) -> None:
    response = await _login(client, "wrong")

    assert response.status_code == 302
    assert response.headers["location"] == "/login"


async def test_the_login_page_names_the_failure_and_keeps_the_username(
    client: httpx.AsyncClient,
) -> None:
    _ = await _login(client, "wrong")

    page = await client.get("/login")

    assert page.json() == {
        "error": "BadCredentialsError",
        "key": "Invalid credentials.",
        "username": "ada",
    }


async def test_a_form_page_still_reads_its_form_after_the_login(
    client: httpx.AsyncClient,
) -> None:
    _ = await _login(client, "secret")

    response = await client.post("/echo", data={"note": "hello"})

    assert response.status_code == 200
    assert response.json() == {"user": "ada", "form": {"note": "hello"}}


async def test_a_json_login_posted_as_its_body_reaches_its_endpoint_as_the_user(
    client: httpx.AsyncClient,
) -> None:
    response = await client.post("/api/login", json={"username": "ada", "password": "secret"})

    assert response.status_code == 200
    assert response.json() == {"user": "ada"}


async def test_a_json_login_with_a_wrong_password_is_refused(client: httpx.AsyncClient) -> None:
    response = await client.post("/api/login", json={"username": "ada", "password": "wrong"})

    assert response.status_code == 401
    assert response.json() == {"error": "The presented credentials are invalid."}


async def test_a_switch_posted_in_a_form_switches_the_user(client: httpx.AsyncClient) -> None:
    _ = await _login(client, "secret")

    switched = await client.post("/", data={"_switch_user": "bob"}, follow_redirects=True)

    assert switched.status_code == 200
    assert switched.json() == {"user": "bob"}
