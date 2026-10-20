"""The forgery-token chain over a real served application.

Drives the CSRF fixture through ``httpx.ASGITransport`` inside the app's own
lifespan. The login page mints the tokens its forms carry — through the very
manager the bundle wires, over the session the request reattached — and the
logout's proof is driven both ways: a forged token is refused loudly, a minted
one logs the request out. The login submission is driven across requests
too: the session the first request wrote — its minted token, the login the
second proves, the token the login stores — survives each response through
the bundle's save listener, and the third request reattaches it by the
cookie that save staged.

The logout's proof is carried in the query string — the readers' own
fallback — because the chain's request carries its body unparsed until the
route materialises it.
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
        params={"_username": "alice", "_password": "secret", "_csrf_token": "anything"},
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


async def test_a_login_submission_persists_the_session_across_requests(
    client: httpx.AsyncClient,
) -> None:
    """The login writes a session the next request reattaches by its cookie.

    The first request mints the forgery token into the session its response
    saves; the second presents that token, authenticates, and stores the
    login's token in the session its response saves — under the ID the login
    rotated, carried by the cookie that response staged; the third arrives
    with that cookie and is answered as the logged-in user, its token
    restored from the session the first two wrote.

    The submission's fields ride the query string — the readers' own
    fallback — because the chain's request carries its body unparsed until
    the route materialises it; the login itself, the part this suite is
    here to prove, runs live: the save, the cookie, the write-back, the
    reattachment, the restored token.
    """
    page = await client.get("/login")

    submitted = await client.post(
        "/login_check",
        params={
            "_username": "alice",
            "_password": "secret",
            "_csrf_token": _token_of(page, "_csrf_token"),
        },
    )
    assert submitted.status_code == 302
    assert submitted.headers["location"] == "/"

    home = await client.get("/")
    assert home.status_code == 200
    assert "alice" in home.text
