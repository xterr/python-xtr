"""The token endpoint, served through a real application."""

from __future__ import annotations

import pytest

from tests.support.served import (
    CLIENT_ID,
    CLIENT_SECRET,
    SCOPE,
    SEED_PATH,
    claims_of,
    int_field,
    json_of,
    served_application,
    serving,
    text_field,
)

pytestmark = pytest.mark.anyio


async def test_a_client_acting_for_itself_is_issued_an_access_token() -> None:
    async with serving(served_application()) as client:
        seeded = await client.post(SEED_PATH)
        answered = await client.post(
            "/token",
            data={
                "grant_type": "client_credentials",
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "scope": SCOPE,
            },
        )

    assert seeded.status_code == 200
    assert answered.status_code == 200
    issued = json_of(answered)
    assert text_field(issued, "token_type") == "Bearer"
    assert int_field(issued, "expires_in") > 0
    assert text_field(issued, "access_token")


async def test_the_token_lasts_as_long_as_the_deployment_configured() -> None:
    # The lifetime travels a long way to get here: the configured value becomes
    # a container parameter, the grant pass tags each flow with it, and the
    # server replays that tag as it enables the grant. Asserting the answer is
    # what proves the whole path, not just its ends.
    async with serving(served_application()) as client:
        _ = await client.post(SEED_PATH)
        issued = json_of(
            await client.post(
                "/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": CLIENT_ID,
                    "client_secret": CLIENT_SECRET,
                },
            ),
        )

    # The shipped default of an hour, give or take the second it took to answer.
    assert int_field(issued, "expires_in") in range(3595, 3601)


async def test_the_token_answer_is_never_cached() -> None:
    # A proxy keeping one caller's token and handing it to another is the
    # whole reason these headers are not optional.
    async with serving(served_application()) as client:
        _ = await client.post(SEED_PATH)
        answered = await client.post(
            "/token",
            data={
                "grant_type": "client_credentials",
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
            },
        )

    assert answered.headers["cache-control"] == "no-store"
    assert answered.headers["pragma"] == "no-cache"


async def test_a_wrong_secret_is_refused_as_an_unauthenticated_client() -> None:
    async with serving(served_application()) as client:
        _ = await client.post(SEED_PATH)
        answered = await client.post(
            "/token",
            data={
                "grant_type": "client_credentials",
                "client_id": CLIENT_ID,
                "client_secret": "not-the-secret",
            },
        )

    assert answered.status_code == 401
    assert text_field(json_of(answered), "error") == "invalid_client"


async def test_a_grant_the_client_is_not_registered_for_is_refused() -> None:
    async with serving(served_application()) as client:
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
    assert text_field(json_of(answered), "error") == "unauthorized_client"


async def test_a_request_naming_no_grant_is_refused() -> None:
    async with serving(served_application()) as client:
        answered = await client.post("/token", data={})

    assert answered.status_code == 400
    assert text_field(json_of(answered), "error") == "unsupported_grant_type"


async def test_a_scope_the_client_is_not_registered_for_is_refused() -> None:
    async with serving(served_application()) as client:
        _ = await client.post(SEED_PATH)
        answered = await client.post(
            "/token",
            data={
                "grant_type": "client_credentials",
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "scope": "write",
            },
        )

    assert answered.status_code == 400
    assert text_field(json_of(answered), "error") == "invalid_scope"


async def test_a_request_naming_no_scope_is_granted_the_clients_registered_scopes() -> None:
    # The protocol's own rule, not a server-wide default: the server sets no
    # default scope, so a request asking for nothing is granted exactly what
    # the client's registration allows. The granted scope is not in the answer
    # — the reference bearer document carries none — it is in the token, which
    # is where a resource server reads it.
    async with serving(served_application()) as client:
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
    granted = claims_of(text_field(json_of(answered), "access_token"))

    assert text_field(granted, "scope") == SCOPE
