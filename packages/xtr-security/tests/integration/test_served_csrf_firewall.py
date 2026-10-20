"""The forgery-token chain over a real served application.

Drives the CSRF fixture through ``httpx.ASGITransport`` inside the app's own
lifespan. The login page mints the tokens its forms carry — through the very
manager the bundle wires, over the session the request reattached — and the
logout's proof is driven both ways: a forged token is refused loudly, a minted
one logs the request out.

The login submission's own forgery check cannot be driven across requests
here: the response-time session save has not landed, so nothing the chain
writes survives the redirect. The check's registration — ahead of the user
load, at the landed listener's own priority — is pinned by the wiring suite;
what this suite pins live is the machinery every request runs: the park, the
manager over it, and the logout's proof through it — carried in the query
string, the readers' own fallback, because the chain's request carries its
body unparsed until the route materialises it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx
import pytest

from tests.fixtures.csrf_app.app import app

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


def _token_of(page: httpx.Response, field: str) -> str:
    """Return the forgery token the page's form carries under ``field``."""
    text = page.text
    return text.split(f'name="{field}" value="', 1)[1].split('"', 1)[0]


async def test_an_anonymous_request_is_redirected_to_the_login_page(
    client: httpx.AsyncClient,
) -> None:
    response = await client.get("/")

    assert response.status_code == 302
    assert response.headers["location"] == "/login"


async def test_the_login_page_mints_its_tokens_through_the_wired_manager(
    client: httpx.AsyncClient,
) -> None:
    response = await client.get("/login")

    assert response.status_code == 200
    assert 'name="_csrf_token" value="' in response.text
    assert 'name="_logout_token" value="' in response.text


async def test_a_form_submission_is_answered_by_the_login_pages_redirect(
    client: httpx.AsyncClient,
) -> None:
    _ = await client.get("/login")

    response = await client.post(
        "/login_check",
        data={"_username": "alice", "_password": "secret", "_csrf_token": "anything"},
    )

    assert response.status_code == 302
    assert response.headers["location"] == "/login"


async def test_a_logout_with_a_forged_token_is_refused_loudly(
    client: httpx.AsyncClient,
) -> None:
    _ = await client.get("/login")

    response = await client.post("/logout", params={"_csrf_token": "forged"})

    assert response.status_code == 403


async def test_a_logout_with_a_minted_token_logs_the_request_out(
    client: httpx.AsyncClient,
) -> None:
    page = await client.get("/login")

    response = await client.post(
        "/logout", params={"_csrf_token": _token_of(page, "_logout_token")}
    )

    assert response.status_code == 302
    assert response.headers["location"] == "/"
