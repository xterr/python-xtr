"""Withdrawing a token, and asking what this server says about one."""

from __future__ import annotations

import pytest

from tests.support.served import (
    CLIENT_ID,
    CLIENT_SECRET,
    SCOPE,
    client_credentials_token,
    json_of,
    served_application,
    serving,
    text_field,
)

pytestmark = pytest.mark.anyio


def _client_auth() -> dict[str, str]:
    """Return the credentials a client authenticates to these endpoints with."""
    return {"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET}


async def test_a_live_token_is_reported_active_with_what_it_carries() -> None:
    async with serving(served_application()) as client:
        token = await client_credentials_token(client)
        answered = await client.post(
            "/introspect",
            data={"token": token, **_client_auth()},
        )

    assert answered.status_code == 200
    document = json_of(answered)
    assert document["active"] is True
    assert text_field(document, "client_id") == CLIENT_ID
    assert text_field(document, "scope") == SCOPE


async def test_withdrawing_a_token_is_answered_as_done() -> None:
    async with serving(served_application()) as client:
        token = await client_credentials_token(client)
        answered = await client.post("/revoke", data={"token": token, **_client_auth()})

    assert answered.status_code == 200


async def test_a_withdrawn_token_is_no_longer_active() -> None:
    async with serving(served_application()) as client:
        token = await client_credentials_token(client)
        _ = await client.post("/revoke", data={"token": token, **_client_auth()})
        answered = await client.post(
            "/introspect",
            data={"token": token, **_client_auth()},
        )

    assert json_of(answered)["active"] is False


async def test_a_token_this_server_cannot_read_is_reported_inactive() -> None:
    # Saying which of unreadable, expired, withdrawn or foreign it was would
    # turn the endpoint into a way of probing what this server holds.
    async with serving(served_application()) as client:
        _ = await client_credentials_token(client)
        answered = await client.post(
            "/introspect",
            data={"token": "not.a.token", **_client_auth()},
        )

    assert answered.status_code == 200
    assert json_of(answered)["active"] is False


async def test_withdrawing_a_token_this_server_cannot_read_is_still_answered_as_done() -> None:
    # Answering anything else would tell a caller whether an arbitrary string
    # is a live token.
    async with serving(served_application()) as client:
        _ = await client_credentials_token(client)
        answered = await client.post(
            "/revoke",
            data={"token": "not.a.token", **_client_auth()},
        )

    assert answered.status_code == 200


async def test_an_unauthenticated_client_may_not_withdraw_a_token() -> None:
    async with serving(served_application()) as client:
        token = await client_credentials_token(client)
        answered = await client.post(
            "/revoke",
            data={"token": token, "client_id": CLIENT_ID, "client_secret": "wrong"},
        )

    assert answered.status_code == 401
    assert text_field(json_of(answered), "error") == "invalid_client"


async def test_an_unauthenticated_client_may_not_ask_about_a_token() -> None:
    async with serving(served_application()) as client:
        token = await client_credentials_token(client)
        answered = await client.post(
            "/introspect",
            data={"token": token, "client_id": CLIENT_ID, "client_secret": "wrong"},
        )

    assert answered.status_code == 401
    assert text_field(json_of(answered), "error") == "invalid_client"


async def test_a_request_naming_no_token_is_refused() -> None:
    async with serving(served_application()) as client:
        _ = await client_credentials_token(client)
        answered = await client.post("/revoke", data=_client_auth())

    assert answered.status_code == 400
    assert text_field(json_of(answered), "error") == "invalid_request"
