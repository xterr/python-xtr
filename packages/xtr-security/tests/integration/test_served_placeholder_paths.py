"""A firewall's login and logout paths read from the environment or from parameters.

A deployment logging out to a separate single-page application's origin names
that origin in its environment. Each path here is a placeholder or a
``%parameter%`` while the container is built, and what a browser is sent to
must be the value it resolves to, never the placeholder's text.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import httpx
import pytest

from tests.fixtures.env_paths_app.app import served
from tests.fixtures.env_paths_app.paths import CHECK_PATH, LOGIN_PATH, LOGOUT_PATH, LOGOUT_TARGET

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

pytestmark = pytest.mark.anyio

_LOGIN = {"_username": "alice", "_password": "secret"}


@pytest.fixture(
    params=["tests.fixtures.env_paths_app", "tests.fixtures.parameter_paths_app"],
    ids=["env", "parameter"],
)
async def client(request: pytest.FixtureRequest) -> AsyncIterator[httpx.AsyncClient]:
    """Serve each fixture's configuration inside its lifespan."""
    app = served(cast("str", request.param))
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as opened:
            yield opened


async def test_an_anonymous_request_is_sent_to_the_login_path_the_value_names(
    client: httpx.AsyncClient,
) -> None:
    response = await client.get("/")

    assert response.status_code == 302
    assert response.headers["location"] == LOGIN_PATH


async def test_a_submission_to_the_check_path_the_value_names_logs_in(
    client: httpx.AsyncClient,
) -> None:
    submitted = await client.post(CHECK_PATH, params=_LOGIN)

    assert submitted.status_code == 302
    assert (await client.get("/")).status_code == 200


async def test_a_logout_at_the_path_the_value_names_redirects_to_the_target_it_names(
    client: httpx.AsyncClient,
) -> None:
    _ = await client.post(CHECK_PATH, params=_LOGIN)

    response = await client.post(LOGOUT_PATH)

    assert response.status_code == 302
    assert response.headers["location"] == LOGOUT_TARGET
    assert (await client.get("/")).status_code == 302
