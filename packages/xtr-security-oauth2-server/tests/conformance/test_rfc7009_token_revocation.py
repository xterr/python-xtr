"""RFC 7009 — OAuth 2.0 Token Revocation.

Where a case comes from the test suite of oauthlib 4.0.0 (145a9a4), whose
``RevocationEndpointTest`` walks the hint values and the error answers, the
test says so.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

import pytest
from fastapi import APIRouter, FastAPI
from xtr_security_http.firewall.firewall import Firewall

from tests.fixtures.oauth2_auth_code_app.config import USER_IDENTIFIER, USER_PASSWORD
from tests.support.served import (
    CLIENT_ID,
    CLIENT_SECRET,
    SCOPE,
    SEED_PATH,
    client_credentials_token,
    json_of,
    oauth2_kernel,
    served_application,
    serving,
    text_field,
)

if TYPE_CHECKING:
    import httpx

pytestmark = pytest.mark.anyio

FIREWALL: Final = "api"

OTHER_CLIENT_ID: Final = "another-confidential-client"
OTHER_CLIENT_SECRET: Final = "another-plaintext-secret"


def _client_auth() -> dict[str, str]:
    """Return the credentials a client authenticates to this endpoint with."""
    return {"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET}


def _api(app: FastAPI) -> None:
    """Mount an API behind the firewall, so a withdrawal can be seen to take."""
    router = APIRouter(prefix="/api", dependencies=[Firewall(FIREWALL)])

    @router.get("/me")
    async def me() -> dict[str, str]:
        return {"read": "yes"}

    app.include_router(router)


def _application() -> FastAPI:
    """Return a deployment whose API is read by its own access tokens."""
    return served_application(
        oauth2_kernel("tests.fixtures.oauth2_firewall_app"),
        extend=_api,
    )


async def _refresh_token(client: httpx.AsyncClient) -> tuple[str, str]:
    """Return a token pair the resource owner's own credentials earned.

    The access token comes back beside the refresh token because the rule about
    cascading revocation is about exactly that pair.
    """
    seeded = await client.post(SEED_PATH, params={"grant": ""})
    assert seeded.status_code == 200, seeded.text
    issued = json_of(
        await client.post(
            "/token",
            data={
                "grant_type": "password",
                "username": USER_IDENTIFIER,
                "password": USER_PASSWORD,
                "scope": SCOPE,
                **_client_auth(),
            },
        ),
    )

    return text_field(issued, "access_token"), text_field(issued, "refresh_token")


def _owner_application() -> FastAPI:
    """Return a deployment that runs the password flow and serves an API."""
    return served_application(
        oauth2_kernel("tests.fixtures.oauth2_auth_code_app"),
        extend=_api,
        dependencies=[Firewall()],
    )


# Section 1 — Introduction


async def test_a_refresh_token_can_be_withdrawn() -> None:
    # "Implementations MUST support the revocation of refresh tokens"
    # (section 1): a refresh token withdrawn here cannot be spent afterwards.
    async with serving(_owner_application()) as client:
        _, refresh = await _refresh_token(client)
        withdrawn = await client.post("/revoke", data={"token": refresh, **_client_auth()})
        spent = await client.post(
            "/token",
            data={"grant_type": "refresh_token", "refresh_token": refresh, **_client_auth()},
        )

    assert withdrawn.status_code == 200
    assert spent.status_code == 400
    assert text_field(json_of(spent), "error") == "invalid_grant"


async def test_an_access_token_can_be_withdrawn() -> None:
    # "and SHOULD support the revocation of access tokens" (section 1).
    async with serving(_application()) as client:
        token = await client_credentials_token(client)
        withdrawn = await client.post("/revoke", data={"token": token, **_client_auth()})
        refused = await client.get("/api/me", headers={"Authorization": f"Bearer {token}"})

    assert withdrawn.status_code == 200
    assert refused.status_code == 401


# Section 2.1 — Revocation Request


async def test_a_request_naming_no_token_is_refused() -> None:
    # "token — REQUIRED. The token that the client wants to get revoked"
    # (section 2.1). Ported from oauthlib's ``test_revoke_unsupported_token``,
    # whose second half posts an empty body.
    async with serving(_application()) as client:
        _ = await client_credentials_token(client)
        answered = await client.post("/revoke", data=_client_auth())

    assert answered.status_code == 400
    assert text_field(json_of(answered), "error") == "invalid_request"


async def test_a_hint_naming_the_wrong_kind_still_finds_the_token() -> None:
    # "If the server is unable to locate the token using the given hint, it
    # MUST extend its search across all of its supported token types" (section
    # 2.1): an access token offered under the refresh-token hint is found all
    # the same.
    async with serving(_application()) as client:
        token = await client_credentials_token(client)
        withdrawn = await client.post(
            "/revoke",
            data={"token": token, "token_type_hint": "refresh_token", **_client_auth()},
        )
        refused = await client.get("/api/me", headers={"Authorization": f"Bearer {token}"})

    assert withdrawn.status_code == 200
    assert refused.status_code == 401


async def test_a_refresh_token_offered_under_the_access_token_hint_is_still_found() -> None:
    # The same rule the other way round (section 2.1).
    async with serving(_owner_application()) as client:
        _, refresh = await _refresh_token(client)
        withdrawn = await client.post(
            "/revoke",
            data={"token": refresh, "token_type_hint": "access_token", **_client_auth()},
        )
        spent = await client.post(
            "/token",
            data={"grant_type": "refresh_token", "refresh_token": refresh, **_client_auth()},
        )

    assert withdrawn.status_code == 200
    assert spent.status_code == 400


async def test_withdrawing_a_refresh_token_also_withdraws_its_access_token() -> None:
    # "If the particular token is a refresh token and the authorization server
    # supports the revocation of access tokens, then the authorization server
    # SHOULD also invalidate all access tokens based on the same authorization
    # grant" (section 2.1).
    async with serving(_owner_application()) as client:
        access, refresh = await _refresh_token(client)
        withdrawn = await client.post("/revoke", data={"token": refresh, **_client_auth()})
        refused = await client.get("/api/me", headers={"Authorization": f"Bearer {access}"})

    assert withdrawn.status_code == 200
    assert refused.status_code == 401


async def test_a_client_must_authenticate_to_withdraw_a_token() -> None:
    # "The authorization server first validates the client credentials ...
    # If this validation fails, the request is refused" (section 2.1), and
    # section 2.2.1 defers the presentation to RFC 6749 section 5.2. Taken
    # from oauthlib's ``test_revoke_token_client_authentication_failed``.
    async with serving(_application()) as client:
        token = await client_credentials_token(client)
        answered = await client.post(
            "/revoke",
            data={"token": token, "client_id": CLIENT_ID, "client_secret": "wrong"},
        )

    assert answered.status_code == 401
    assert text_field(json_of(answered), "error") == "invalid_client"


async def test_a_token_belonging_to_another_client_is_answered_as_done() -> None:
    # Section 2.1 has the server verify "whether the token was issued to the
    # client making the revocation request", and refuse if not. This server
    # answers 200 and withdraws nothing: a refusal would tell the asking client
    # that the token it guessed exists. Recorded as a deliberate deviation in
    # the plan's Phase 5.
    async with serving(_application()) as client:
        token = await client_credentials_token(client)
        seeded = await client.post(
            SEED_PATH,
            params={"identifier": OTHER_CLIENT_ID, "secret": OTHER_CLIENT_SECRET},
        )
        assert seeded.status_code == 200, seeded.text
        answered = await client.post(
            "/revoke",
            data={
                "token": token,
                "client_id": OTHER_CLIENT_ID,
                "client_secret": OTHER_CLIENT_SECRET,
            },
        )
        still_open = await client.get("/api/me", headers={"Authorization": f"Bearer {token}"})

    assert answered.status_code == 200
    assert still_open.status_code == 200


# Section 2.2 — Revocation Response


async def test_a_token_this_server_never_issued_is_answered_as_done() -> None:
    # "The authorization server responds with HTTP status code 200 if the token
    # has been revoked successfully or if the client submitted an invalid
    # token" (section 2.2). Taken from oauthlib's ``test_revoke_token``.
    async with serving(_application()) as client:
        _ = await client_credentials_token(client)
        answered = await client.post("/revoke", data={"token": "not.a.token", **_client_auth()})

    assert answered.status_code == 200


async def test_withdrawing_the_same_token_twice_is_answered_as_done_both_times() -> None:
    # The same rule: a token already withdrawn is an invalid token now
    # (section 2.2).
    async with serving(_application()) as client:
        token = await client_credentials_token(client)
        first = await client.post("/revoke", data={"token": token, **_client_auth()})
        again = await client.post("/revoke", data={"token": token, **_client_auth()})

    assert first.status_code == 200
    assert again.status_code == 200


async def test_a_hint_value_this_server_does_not_know_is_ignored() -> None:
    # "An invalid token type hint value is ignored by the authorization server
    # and does not influence the revocation response" (section 2.2). Ported
    # from oauthlib's ``test_revoke_token``, which walks
    # ``('access_token', 'refresh_token', 'invalid')``.
    async with serving(_application()) as client:
        token = await client_credentials_token(client)
        withdrawn = await client.post(
            "/revoke",
            data={"token": token, "token_type_hint": "nothing-like-a-type", **_client_auth()},
        )
        refused = await client.get("/api/me", headers={"Authorization": f"Bearer {token}"})

    assert withdrawn.status_code == 200
    assert refused.status_code == 401


async def test_the_answer_to_a_withdrawal_may_not_be_cached() -> None:
    # The answer is about a credential, so nothing may keep it; the standard
    # requires the same of every token answer through RFC 6749 section 5.1.
    async with serving(_application()) as client:
        token = await client_credentials_token(client)
        answered = await client.post("/revoke", data={"token": token, **_client_auth()})

    assert answered.headers["cache-control"] == "no-store"


async def test_the_withdrawal_takes_effect_at_once() -> None:
    # "The invalidation takes place immediately, and the token cannot be used
    # again after the revocation" (section 2.1) — read at the one place a
    # client could notice, the resource it was using the token at.
    async with serving(_application()) as client:
        token = await client_credentials_token(client)
        opened = await client.get("/api/me", headers={"Authorization": f"Bearer {token}"})
        _ = await client.post("/revoke", data={"token": token, **_client_auth()})
        closed = await client.get("/api/me", headers={"Authorization": f"Bearer {token}"})

    assert opened.status_code == 200
    assert closed.status_code == 401
