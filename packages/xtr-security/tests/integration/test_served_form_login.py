"""The form login, the JSON login and the switch, over a served app, on either session storage.

Drives the form-login fixture through ``httpx.ASGITransport`` inside the app's
own lifespan, every submission posted the way a browser or a client posts it:
the form login's fields, the switch's username and the page's own form ride
the request's body as a form, and the JSON login's document rides it as JSON.
The chain reads each body before it asks for the fields in it, and the route
behind the firewall still reads the body it was posted.

Every case runs twice: once over the fixture's cache-pool session storage,
which keeps a session as JSON and nothing else, and once over the memory one
its twin fixture registers. The answers are the same on both, because what the
firewall keeps in a session — the token and the last error — is JSON either
way.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, cast

import httpx
import pytest

from tests.fixtures.form_login_app.app import app as cache_pool_app
from tests.fixtures.form_login_memory_app.app import app as memory_app

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Mapping

    from fastapi import FastAPI

pytestmark = pytest.mark.anyio

#: The two applications, one per session storage, each case is served by.
_APPS: Final[Mapping[str, FastAPI]] = {"cache_pool": cache_pool_app, "memory": memory_app}


@pytest.fixture(params=list(_APPS))
async def client(request: pytest.FixtureRequest) -> AsyncIterator[httpx.AsyncClient]:
    """Serve the fixture app over one session storage, inside its lifespan."""
    app = _APPS[cast("str", request.param)]
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


async def test_the_request_after_a_login_is_the_user_who_logged_in(
    client: httpx.AsyncClient,
) -> None:
    login = await _login(client, "secret")

    home = await client.get("/")

    assert login.status_code == 302
    assert home.status_code == 200
    assert home.json() == {"user": "ada"}


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


async def test_the_login_page_shows_the_failure_once(client: httpx.AsyncClient) -> None:
    _ = await _login(client, "wrong")
    _ = await client.get("/login")

    again = await client.get("/login")

    assert again.json() == {"error": None, "key": None, "username": "ada"}


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


async def test_a_json_login_is_kept_for_the_apis_next_request(client: httpx.AsyncClient) -> None:
    _ = await client.post("/api/login", json={"username": "ada", "password": "secret"})

    me = await client.get("/api/me")

    assert me.status_code == 200
    assert me.json() == {"user": "ada"}


async def test_a_json_login_with_a_wrong_password_is_refused(client: httpx.AsyncClient) -> None:
    response = await client.post("/api/login", json={"username": "ada", "password": "wrong"})

    assert response.status_code == 401
    assert response.json() == {"error": "The presented credentials are invalid."}


async def test_a_switch_posted_in_a_form_switches_the_user(client: httpx.AsyncClient) -> None:
    _ = await _login(client, "secret")

    switched = await client.post("/", data={"_switch_user": "bob"}, follow_redirects=True)

    assert switched.status_code == 200
    assert switched.json() == {"user": "bob"}


async def test_a_switch_is_kept_and_its_exit_restores_the_original_user(
    client: httpx.AsyncClient,
) -> None:
    _ = await _login(client, "secret")
    _ = await client.get("/", params={"_switch_user": "bob"})
    kept = await client.get("/")

    exited = await client.get("/", params={"_switch_user": "_exit"}, follow_redirects=True)

    assert kept.json() == {"user": "bob"}
    assert exited.status_code == 200
    assert exited.json() == {"user": "ada"}


async def test_a_logout_clears_the_session(client: httpx.AsyncClient) -> None:
    _ = await _login(client, "secret")
    logout = await client.get("/logout")

    home = await client.get("/")

    assert logout.status_code == 302
    assert logout.headers["location"] == "/"
    assert home.status_code == 302
    assert home.headers["location"] == "/login"
