"""An endpoint a deployment does not serve says so in the answer.

The router is built when the module is imported, before any configuration has
been read, so it cannot leave a path out. A deployment that turned an endpoint
off is therefore indistinguishable, from a client's side, from a server that
never had it.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI

from tests.support.served import (
    CLIENT_ID,
    CLIENT_SECRET,
    SEED_PATH,
    json_of,
    oauth2_kernel,
    served_application,
    serving,
    text_field,
)

pytestmark = pytest.mark.anyio


def _application() -> FastAPI:
    """Return a deployment with every optional endpoint turned off."""
    return served_application(oauth2_kernel("tests.fixtures.oauth2_minimal_app"))


@pytest.mark.parametrize(
    "path",
    ["/revoke", "/introspect", "/device-code"],
)
async def test_an_endpoint_that_was_turned_off_is_not_found(path: str) -> None:
    async with serving(_application()) as client:
        answered = await client.post(path, data={})

    assert answered.status_code == 404


async def test_a_server_that_does_not_describe_itself_is_not_found() -> None:
    async with serving(_application()) as client:
        answered = await client.get("/.well-known/oauth-authorization-server")

    assert answered.status_code == 404


async def test_the_keys_are_published_whatever_else_is_turned_off() -> None:
    # There is no setting for this one: a token is a signed document, so
    # anything reading one needs the key to check it against.
    async with serving(_application()) as client:
        answered = await client.get("/.well-known/jwks.json")

    assert answered.status_code == 200
    assert json_of(answered)["keys"]


async def test_the_flow_the_deployment_did_keep_still_issues_tokens() -> None:
    async with serving(_application()) as client:
        _ = await client.post(SEED_PATH)
        answered = await client.post(
            "/token",
            data={
                "grant_type": "client_credentials",
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
            },
        )

    assert answered.status_code == 200
    assert text_field(json_of(answered), "token_type") == "Bearer"


async def test_a_flow_the_deployment_turned_off_is_not_run() -> None:
    async with serving(_application()) as client:
        _ = await client.post(SEED_PATH)
        answered = await client.post(
            "/token",
            data={
                "grant_type": "refresh_token",
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "refresh_token": "whatever",
            },
        )

    assert answered.status_code == 400
    assert text_field(json_of(answered), "error") == "unsupported_grant_type"
