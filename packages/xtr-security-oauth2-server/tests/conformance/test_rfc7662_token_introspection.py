"""RFC 7662 — OAuth 2.0 Token Introspection.

Where a case comes from the test suite of oauthlib 4.0.0 (145a9a4), whose
``IntrospectEndpointTest`` fixes the shape of the answer for a token that is
not active, the test says so.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

import pytest
from fastapi import FastAPI

from tests.fixtures.oauth2_conformance_app.config import USER_IDENTIFIER, USER_PASSWORD
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

OTHER_CLIENT_ID: Final = "another-confidential-client"
OTHER_CLIENT_SECRET: Final = "another-plaintext-secret"


def _client_auth() -> dict[str, str]:
    """Return the credentials a client authenticates to this endpoint with."""
    return {"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET}


def _owner_application() -> FastAPI:
    """Return a deployment that runs the password flow with introspection on."""
    return served_application(oauth2_kernel("tests.fixtures.oauth2_conformance_app"))


async def _refresh_token(client: httpx.AsyncClient) -> str:
    """Return a refresh token the resource owner's own credentials earned."""
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

    return text_field(issued, "refresh_token")


# Section 2.1 — Introspection Request


async def test_a_request_naming_no_token_is_refused() -> None:
    # "token — REQUIRED. The string value of the token" (section 2.1). Ported
    # from oauthlib's ``test_introspect_unsupported_token``, whose second half
    # posts an empty body.
    async with serving(served_application()) as client:
        _ = await client_credentials_token(client)
        answered = await client.post("/introspect", data=_client_auth())

    assert answered.status_code == 400
    assert text_field(json_of(answered), "error") == "invalid_request"


async def test_nobody_may_ask_without_authorization() -> None:
    # "To prevent token scanning attacks, the endpoint MUST also require some
    # form of authorization to access this endpoint, such as client
    # authentication as described in OAuth 2.0" (section 2.1).
    async with serving(served_application()) as client:
        token = await client_credentials_token(client)
        answered = await client.post("/introspect", data={"token": token})

    assert answered.status_code in {400, 401}
    assert "active" not in json_of(answered)


async def test_a_hint_naming_the_wrong_kind_still_finds_the_token() -> None:
    # "If the server is unable to locate the token using the given hint, it
    # MUST extend its search across all of its supported token types" (section
    # 2.1). Ported from oauthlib's ``test_introspect_token_nohint``.
    async with serving(served_application()) as client:
        token = await client_credentials_token(client)
        answered = await client.post(
            "/introspect",
            data={"token": token, "token_type_hint": "refresh_token", **_client_auth()},
        )

    assert answered.status_code == 200
    assert json_of(answered)["active"] is True


async def test_a_refresh_token_is_read_as_well_as_an_access_token() -> None:
    # Both token types this server issues are "supported token types" for the
    # purposes of section 2.1, so a refresh token is read as well.
    async with serving(_owner_application()) as client:
        refresh = await _refresh_token(client)
        answered = await client.post(
            "/introspect",
            data={"token": refresh, **_client_auth()},
        )

    assert answered.status_code == 200
    document = json_of(answered)
    assert document["active"] is True
    assert text_field(document, "client_id") == CLIENT_ID


# Section 2.2 — Introspection Response


async def test_a_live_token_is_reported_active_with_what_it_carries() -> None:
    # "active — REQUIRED. Boolean indicator of whether or not the presented
    # token is currently active", beside the ``scope``, ``client_id``,
    # ``token_type``, ``exp``, ``iat``, ``sub``, ``aud``, ``iss`` and ``jti``
    # of section 2.2.
    async with serving(served_application()) as client:
        token = await client_credentials_token(client)
        answered = await client.post("/introspect", data={"token": token, **_client_auth()})

    document = json_of(answered)
    assert document["active"] is True
    assert text_field(document, "scope") == SCOPE
    assert text_field(document, "client_id") == CLIENT_ID
    assert text_field(document, "token_type") == "Bearer"
    assert text_field(document, "jti")
    assert isinstance(document["exp"], int)
    assert isinstance(document["iat"], int)


async def test_the_answer_is_a_json_document() -> None:
    # "The server responds with a JSON object [RFC7159] in "application/json"
    # format" (section 2.2).
    async with serving(served_application()) as client:
        token = await client_credentials_token(client)
        answered = await client.post("/introspect", data={"token": token, **_client_auth()})

    assert answered.headers["content-type"].startswith("application/json")


async def test_a_token_this_server_cannot_read_is_reported_inactive() -> None:
    # "If the introspection call is properly authorized but the token is not
    # active, does not exist on this server, or the protected resource is not
    # allowed to introspect this particular token, then the authorization
    # server MUST return an introspection response with the "active" field set
    # to "false"" (section 2.2). Taken from oauthlib's
    # ``test_introspect_token_false``.
    async with serving(served_application()) as client:
        _ = await client_credentials_token(client)
        answered = await client.post(
            "/introspect",
            data={"token": "not.a.token", **_client_auth()},
        )

    assert answered.status_code == 200
    assert json_of(answered)["active"] is False


async def test_a_withdrawn_token_is_reported_inactive() -> None:
    # The same rule for a token this server did issue and has since withdrawn
    # (section 2.2).
    async with serving(served_application()) as client:
        token = await client_credentials_token(client)
        _ = await client.post("/revoke", data={"token": token, **_client_auth()})
        answered = await client.post("/introspect", data={"token": token, **_client_auth()})

    assert json_of(answered)["active"] is False


async def test_an_inactive_token_is_described_no_further() -> None:
    # "the authorization server SHOULD NOT include any additional information
    # about an inactive token, including why the token is inactive" (section
    # 2.2), which the standard's own example answers as ``{"active": false}``.
    async with serving(served_application()) as client:
        _ = await client_credentials_token(client)
        answered = await client.post(
            "/introspect",
            data={"token": "not.a.token", **_client_auth()},
        )

    assert json_of(answered) == {"active": False}


async def test_a_client_cannot_make_a_token_look_active_by_asking_about_it() -> None:
    # The ``active`` field is the server's to decide: a request naming it is a
    # parameter this server does not know, and section 2.1 defines only
    # ``token`` and ``token_type_hint``. Ported from oauthlib's
    # ``test_introspect_token_claims_spoof_active``.
    async with serving(served_application()) as client:
        _ = await client_credentials_token(client)
        answered = await client.post(
            "/introspect",
            data={"token": "not.a.token", "active": "true", **_client_auth()},
        )

    assert json_of(answered)["active"] is False


async def test_the_answer_may_not_be_cached_indefinitely() -> None:
    # "the response MUST NOT be cached beyond the time indicated therein"
    # (section 4): this server indicates none, so nothing may keep it.
    async with serving(served_application()) as client:
        token = await client_credentials_token(client)
        answered = await client.post("/introspect", data={"token": token, **_client_auth()})

    assert answered.headers["cache-control"] == "no-store"


async def test_an_access_token_issued_to_another_client_is_still_read() -> None:
    # Section 2.2 lets a server answer "active": false for "a token the
    # protected resource is not allowed to know about", and this server does
    # not: an access token is read for what it says, whichever client asks,
    # since it is a signed document any resource server reads on its own. A
    # refresh token is the other way round, because it was sealed for one
    # client.
    async with serving(served_application()) as client:
        token = await client_credentials_token(client)
        seeded = await client.post(
            SEED_PATH,
            params={"identifier": OTHER_CLIENT_ID, "secret": OTHER_CLIENT_SECRET},
        )
        assert seeded.status_code == 200, seeded.text
        answered = await client.post(
            "/introspect",
            data={
                "token": token,
                "client_id": OTHER_CLIENT_ID,
                "client_secret": OTHER_CLIENT_SECRET,
            },
        )

    assert answered.status_code == 200
    document = json_of(answered)
    assert document["active"] is True
    # Whose token it is, is said plainly rather than hidden.
    assert text_field(document, "client_id") == CLIENT_ID


async def test_a_refresh_token_sealed_for_another_client_is_reported_inactive() -> None:
    # The other half of the same reading (section 2.2): a refresh token names
    # the client it was sealed for, so another client asking learns nothing.
    async with serving(_owner_application()) as client:
        refresh = await _refresh_token(client)
        seeded = await client.post(
            SEED_PATH,
            params={"identifier": OTHER_CLIENT_ID, "secret": OTHER_CLIENT_SECRET},
        )
        assert seeded.status_code == 200, seeded.text
        answered = await client.post(
            "/introspect",
            data={
                "token": refresh,
                "client_id": OTHER_CLIENT_ID,
                "client_secret": OTHER_CLIENT_SECRET,
            },
        )

    assert answered.status_code == 200
    assert json_of(answered) == {"active": False}


# Section 2.3 — Error Response


async def test_a_client_whose_credentials_are_wrong_is_told_so() -> None:
    # "If the protected resource uses OAuth 2.0 client credentials to
    # authenticate to the introspection endpoint and its credentials are
    # invalid, the authorization server responds with an HTTP 401
    # (Unauthorized)" (section 2.3). Taken from oauthlib's
    # ``test_introspect_token_client_authentication_failed``.
    async with serving(served_application()) as client:
        token = await client_credentials_token(client)
        answered = await client.post(
            "/introspect",
            data={"token": token, "client_id": CLIENT_ID, "client_secret": "wrong"},
        )

    assert answered.status_code == 401
    assert text_field(json_of(answered), "error") == "invalid_client"


async def test_asking_about_an_inactive_token_is_not_an_error() -> None:
    # "a properly formed and authorized query for an inactive or otherwise
    # invalid token ... is not considered an error response by this
    # specification. In these cases, the authorization server MUST instead
    # respond with an introspection response with the "active" field set to
    # "false"" (section 2.3).
    async with serving(served_application()) as client:
        token = await client_credentials_token(client)
        _ = await client.post("/revoke", data={"token": token, **_client_auth()})
        answered = await client.post("/introspect", data={"token": token, **_client_auth()})

    assert answered.status_code == 200
    assert "error" not in json_of(answered)
