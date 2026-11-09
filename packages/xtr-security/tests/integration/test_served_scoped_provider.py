"""A user provider and a user checker of the request, over a served app.

Drives the scoped-provider fixture through ``httpx.ASGITransport`` inside the
app's own lifespan. The provider and the checker record every question by the
identity of the instance asked, so each case reads which instance answered:
the one built for the request it was asked in, and never one another request
built.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import anyio
import httpx
import pytest
from xtr_dependency_injection import Kernel

from tests.fixtures.scoped_provider_app.app import app
from tests.fixtures.scoped_provider_app.bundles import BUNDLES
from tests.fixtures.scoped_provider_app.config import PERSISTENT_ENV
from tests.fixtures.scoped_provider_app.services import PASSWORD, RECORDED

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

pytestmark = pytest.mark.anyio

_ADA = {"x-username": "ada", "x-password": PASSWORD}


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    """Serve the fixture app inside its lifespan, with nothing recorded yet."""
    RECORDED.reset()
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as opened:
            yield opened


def _only_provider() -> int:
    """Return the one provider built since the last reset."""
    assert len(RECORDED.providers) == 1
    return RECORDED.providers[0]


def test_remembered_logins_kept_in_series_build_over_a_scoped_provider() -> None:
    _ = Kernel(
        "tests.fixtures.scoped_provider_app", env=PERSISTENT_ENV, debug=True, bundles=BUNDLES
    ).build()


async def test_the_firewalls_listener_loads_the_user_through_the_requests_provider(
    client: httpx.AsyncClient,
) -> None:
    response = await client.get("/loaderless/me", headers=_ADA)

    assert response.status_code == 200
    assert response.json() == {"user": "ada"}
    assert RECORDED.loads == [("ada", _only_provider())]


async def test_a_rehashed_password_is_stored_through_the_requests_provider(
    client: httpx.AsyncClient,
) -> None:
    _ = await client.get("/loaderless/me", headers=_ADA)

    assert RECORDED.upgrades == [_only_provider()]


async def test_the_scoped_checker_runs_before_and_after_on_one_instance(
    client: httpx.AsyncClient,
) -> None:
    _ = await client.get("/loaderless/me", headers=_ADA)

    assert [kind for kind, _ in RECORDED.checks] == ["pre", "post"]
    assert len({checker for _, checker in RECORDED.checks}) == 1


async def test_each_request_gets_its_own_provider(client: httpx.AsyncClient) -> None:
    _ = await client.get("/loaderless/me", headers=_ADA)
    _ = await client.get("/loaderless/me", headers=_ADA)

    first, second = RECORDED.providers
    assert first != second
    assert [provider for _, provider in RECORDED.loads] == [first, second]
    assert len(set(RECORDED.units)) == len(RECORDED.units)


async def test_concurrent_requests_keep_their_own_provider(client: httpx.AsyncClient) -> None:
    statuses: list[int] = []

    async def call() -> None:
        statuses.append((await client.get("/loaderless/me", headers=_ADA)).status_code)

    async with anyio.create_task_group() as group:
        for _ in range(3):
            _ = group.start_soon(call)

    assert statuses == [200, 200, 200]
    assert len(set(RECORDED.providers)) == 3
    assert {provider for _, provider in RECORDED.loads} == set(RECORDED.providers)


async def test_a_bearer_request_loads_its_user_through_the_requests_provider(
    client: httpx.AsyncClient,
) -> None:
    response = await client.get("/api/me", headers={"authorization": "Bearer ada"})

    assert response.status_code == 200
    assert response.json() == {"user": "ada"}
    assert RECORDED.loads == [("ada", _only_provider())]


async def test_a_chain_over_a_scoped_provider_loads_through_it(
    client: httpx.AsyncClient,
) -> None:
    response = await client.get("/chained/me", auth=("ada", PASSWORD))

    assert response.status_code == 200
    assert response.json() == {"user": "ada"}
    assert RECORDED.loads == [("ada", _only_provider())]


async def test_a_form_login_loads_and_checks_the_user_on_the_requests_services(
    client: httpx.AsyncClient,
) -> None:
    response = await client.post("/login_check", params={"_username": "ada", "_password": PASSWORD})

    assert response.status_code == 302
    assert RECORDED.loads == [("ada", _only_provider())]
    assert [kind for kind, _ in RECORDED.checks] == ["pre", "post"]


async def test_the_login_is_kept_for_the_next_request_on_a_new_provider(
    client: httpx.AsyncClient,
) -> None:
    _ = await client.post("/login_check", params={"_username": "ada", "_password": PASSWORD})

    home = await client.get("/")

    assert home.json() == {"user": "ada"}
    assert len(set(RECORDED.providers)) == len(RECORDED.providers) == 2


async def test_a_json_login_answers_through_the_requests_provider(
    client: httpx.AsyncClient,
) -> None:
    response = await client.post("/json_login", json={"username": "ada", "password": PASSWORD})

    assert response.status_code == 200
    assert response.json() == {"user": "ada"}
    assert RECORDED.loads == [("ada", _only_provider())]


async def test_a_remembered_login_sets_and_a_logout_clears_the_cookie(
    client: httpx.AsyncClient,
) -> None:
    login = await client.post("/login_check", params={"_username": "ada", "_password": PASSWORD})
    logout = await client.get("/logout")

    assert "REMEMBERME=" in cast("str", login.headers.get("set-cookie", ""))
    assert "REMEMBERME=deleted" in cast("str", logout.headers.get("set-cookie", ""))


async def test_a_forged_token_is_refused_before_any_user_is_loaded(
    client: httpx.AsyncClient,
) -> None:
    attempt = await client.post(
        "/guarded/login_check",
        params={"_username": "ada", "_password": PASSWORD, "_csrf_token": "forged"},
    )
    page = await client.get("/guarded/login")

    assert attempt.status_code == 302
    assert page.json() == {"error": "InvalidCsrfTokenError"}
    assert RECORDED.loads == []


async def test_a_throttled_attempt_is_refused_before_any_user_is_loaded(
    client: httpx.AsyncClient,
) -> None:
    query = {"_username": "ada", "_password": PASSWORD, "_csrf_token": "forged"}
    _ = await client.post("/guarded/login_check", params=query)

    _ = await client.post("/guarded/login_check", params=query)
    page = await client.get("/guarded/login")

    assert page.json() == {"error": "TooManyLoginAttemptsAuthenticationError"}
    assert RECORDED.loads == []
