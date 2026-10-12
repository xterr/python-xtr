"""The flow for something that cannot show a browser, served for real.

A device asks for a pair of codes, shows one to its owner, and polls while the
owner approves somewhere else. Approving is the application's to do — there is
no endpoint for it, because the page a person types the code into is theirs —
so the test application exposes one, standing where that page would.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

import pytest
from fastapi import FastAPI
from xtr_dependency_injection import Injected
from xtr_security_oauth2_server_core.authorization_server import AuthorizationServer
from xtr_security_oauth2_server_core.oauth2_grants import OAuth2Grants

from tests.support.served import (
    CLIENT_ID,
    CLIENT_SECRET,
    SEED_PATH,
    int_field,
    json_of,
    seed_any_grant_client,
    served_application,
    serving,
    text_field,
)

if TYPE_CHECKING:
    import httpx

pytestmark = pytest.mark.anyio

#: Who approves, as the verification page would report them.
OWNER: Final = "ada"

#: Where the test application's stand-in for a verification page lives.
APPROVE_PATH: Final = "/approve-device"


def _verification(app: FastAPI) -> None:
    """Mount the application's stand-in for a device verification page."""

    @app.post(APPROVE_PATH)
    async def approve(
        server: Injected[AuthorizationServer],
        device_code: str,
        *,
        user_id: str = OWNER,
        approved: bool = True,
    ) -> dict[str, str]:
        await server.complete_device_authorization_request(device_code, user_id, approved)

        return {"recorded": "yes"}


def _application() -> FastAPI:
    """Return the served application with a verification page of its own."""
    return served_application(extend=_verification)


async def _device_codes(client: httpx.AsyncClient) -> tuple[str, str]:
    """Ask for the pair of codes, and return the device code and the user code."""
    await seed_any_grant_client(client)
    answered = await client.post(
        "/device-code",
        data={"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET},
    )
    assert answered.status_code == 200, answered.text
    issued = json_of(answered)

    return text_field(issued, "device_code"), text_field(issued, "user_code")


async def _poll(client: httpx.AsyncClient, device_code: str) -> httpx.Response:
    """Poll the token endpoint the way a device does."""
    return await client.post(
        "/token",
        data={
            "grant_type": OAuth2Grants.DEVICE_CODE,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "device_code": device_code,
        },
    )


async def test_a_device_is_given_a_code_to_poll_with_and_one_to_show() -> None:
    async with serving(_application()) as client:
        await seed_any_grant_client(client)
        answered = await client.post(
            "/device-code",
            data={"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET},
        )

    assert answered.status_code == 200
    issued = json_of(answered)
    assert text_field(issued, "device_code")
    # Short enough for somebody to read off a screen and type elsewhere.
    assert text_field(issued, "user_code")
    assert text_field(issued, "verification_uri")
    assert int_field(issued, "expires_in") > 0
    assert int_field(issued, "interval") > 0


async def test_a_device_polling_before_anyone_approved_is_told_to_wait() -> None:
    async with serving(_application()) as client:
        device_code, _ = await _device_codes(client)
        answered = await _poll(client, device_code)

    assert answered.status_code == 400
    assert text_field(json_of(answered), "error") == "authorization_pending"


async def test_a_device_polling_again_too_soon_is_told_to_slow_down() -> None:
    # What the second answer proves: the first poll's time was written down
    # even though that poll was answered with an error. Rolling it back would
    # make a device able to poll as fast as it liked.
    async with serving(_application()) as client:
        device_code, _ = await _device_codes(client)
        first = await _poll(client, device_code)
        second = await _poll(client, device_code)

    assert text_field(json_of(first), "error") == "authorization_pending"
    assert text_field(json_of(second), "error") == "slow_down"


async def test_an_approved_device_is_issued_a_token() -> None:
    async with serving(_application()) as client:
        device_code, _ = await _device_codes(client)
        recorded = await client.post(APPROVE_PATH, params={"device_code": device_code})
        answered = await _poll(client, device_code)

    assert recorded.status_code == 200
    assert answered.status_code == 200
    issued = json_of(answered)
    assert text_field(issued, "token_type") == "Bearer"
    assert text_field(issued, "access_token")


async def test_a_refused_device_is_told_the_owner_said_no() -> None:
    async with serving(_application()) as client:
        device_code, _ = await _device_codes(client)
        _ = await client.post(
            APPROVE_PATH,
            params={"device_code": device_code, "approved": False},
        )
        answered = await _poll(client, device_code)

    assert answered.status_code != 200
    assert text_field(json_of(answered), "error") == "access_denied"


async def test_a_device_code_this_server_never_issued_is_refused() -> None:
    async with serving(_application()) as client:
        await seed_any_grant_client(client)
        answered = await _poll(client, "not-a-device-code")

    assert answered.status_code != 200
    assert text_field(json_of(answered), "error") != "authorization_pending"


async def test_the_pair_of_codes_is_issued_without_a_client_secret() -> None:
    # A device is a public client as often as not: RFC 8628's request names the
    # client, and a device holding no secret still has to be able to start.
    async with serving(_application()) as client:
        _ = await client.post(
            SEED_PATH,
            params={"identifier": "a-device-client", "secret": "", "grant": ""},
        )
        answered = await client.post("/device-code", data={"client_id": "a-device-client"})

    assert answered.status_code == 200
    assert text_field(json_of(answered), "device_code")
