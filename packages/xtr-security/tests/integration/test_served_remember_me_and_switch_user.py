"""The remembered login, the switch and the channel redirect, over a served app.

Drives the fixture through ``httpx.ASGITransport`` inside the app's own
lifespan. The remember-me proof runs across two clients: the login that
stages the cookie on one, and a fresh client — no session of its own —
that presents the cookie and is answered as the user it remembers. The
switch proof runs on one session: the switched request names the target
user, the exit names the original one. The channel proof asks the page the
channel rule guards over plain HTTP and is redirected to its HTTPS spelling.

The login submission's fields ride the query string — the readers' own
fallback — because the chain's request carries its body unparsed until the
route materialises it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from urllib.parse import unquote

import httpx
import pytest

from tests.fixtures.remember_me_app.app import app

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


def _fresh_client() -> httpx.AsyncClient:
    """A client sharing the app's lifespan but holding no cookies of its own."""
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app, raise_app_exceptions=False),
        base_url="http://test",
    )


async def _login(
    client: httpx.AsyncClient,
    *,
    remember: bool = False,
    username: str = "alice",
) -> httpx.Response:
    """Submit the login form, optionally asking to be remembered."""
    query = {"_username": username, "_password": "secret"}
    if remember:
        query["_remember_me"] = "1"
    return await client.post("/login_check", params=query)


async def test_a_login_asking_to_be_remembered_stages_the_cookie(client: httpx.AsyncClient) -> None:
    """The cookie the login stages rides the redirect the login answers with."""
    response = await _login(client, remember=True)

    assert response.status_code == 302
    cookie = cast("str", response.headers.get("set-cookie", ""))
    assert "REMEMBERME=" in cookie
    # The clear-then-create order stages the fresh cookie last: what leaves
    # is the new value, not the deletion that preceded it.
    assert "REMEMBERME=deleted" not in cookie


async def test_a_login_without_the_ask_stages_no_cookie(client: httpx.AsyncClient) -> None:
    """A login without the ask still drops any stale cookie it carried."""

    # The set listener clears first, always, then creates only for a login
    # that asked — so a no-ask login answers with the deletion of whatever
    # cookie the browser still held.
    response = await _login(client)

    assert response.status_code == 302
    assert "REMEMBERME=deleted" in response.headers.get("set-cookie", "")


async def test_the_cookie_authenticates_a_client_with_no_session_of_its_own(
    client: httpx.AsyncClient,
) -> None:
    """A fresh client presenting the cookie is answered as the user it remembers.

    The three-request persistence the stateful machinery proves, read from
    the other side: the session the login wrote never reaches this client —
    only the cookie does — and the remembered login is what authenticates.
    """
    login = await _login(client, remember=True)
    staged = [
        part
        for part in login.headers["set-cookie"].split(",")
        if part.strip().startswith("REMEMBERME=") and "deleted" not in part
    ]
    cookie = staged[0].strip().split(";", 1)[0]
    name, _, value = cookie.partition("=")

    async with _fresh_client() as fresh:
        # The staged value rides the ``Set-Cookie`` header percent-encoded;
        # the browser carries it back exactly as it was written, so the
        # client here presents the value it read, unquoted.
        fresh.cookies.set(name, unquote(value))
        home = await fresh.get("/")

    assert home.status_code == 200
    assert "<p>alice</p>" in home.text


async def test_a_switch_names_the_target_user_and_the_exit_restores_the_original(
    client: httpx.AsyncClient,
) -> None:
    """The switch step changes the user under the request's own feet."""
    _ = await _login(client)

    switched = await client.get("/", params={"_switch_user": "bob"}, follow_redirects=True)
    assert switched.status_code == 200
    assert "<p>bob</p>" in switched.text

    exited = await client.get("/", params={"_switch_user": "_exit"}, follow_redirects=True)
    assert exited.status_code == 200
    assert "<p>alice</p>" in exited.text


async def test_a_switch_without_the_role_is_refused(client: httpx.AsyncClient) -> None:
    """A caller without the switching role is refused, loudly, through the exception listener."""
    _ = await _login(client, username="bob")

    refused = await client.get("/", params={"_switch_user": "alice"})

    assert refused.status_code == 403


async def test_a_page_the_channel_rule_guards_redirects_to_https(client: httpx.AsyncClient) -> None:
    """The channel step answers a plain-HTTP request for the guarded page."""
    response = await client.get("/secure", follow_redirects=False)

    assert response.status_code == 301
    assert response.headers["location"] == "https://test/secure"
