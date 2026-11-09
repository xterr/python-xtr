"""OpenID Connect Core 1.0 — the userinfo endpoint (Section 5.3) and the scope claims (5.4).

The deployment puts its access tokens' firewall in front of the endpoint and
names an identity provider holding alice. What the endpoint answers is read
off the wire and by the repository's own relying party, whose userinfo reader
finds the endpoint where the configuration document says it is.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

import pytest

from tests.fixtures.openid_app.config import (
    ALGORITHM,
    IDENTITY_PROVIDER_ENV,
    USER_IDENTIFIER,
    USER_PASSWORD,
    USERINFO_ENV,
)
from tests.support.relying_party import relying_party_of
from tests.support.served import (
    SERVICE_CLIENT_ID,
    SERVICE_CLIENT_SECRET,
    claims_of,
    json_of,
    openid_kernel,
    served_application,
    serving,
    text_field,
)
from tests.support.sign_in import signed_in

if TYPE_CHECKING:
    import httpx

pytestmark = pytest.mark.anyio

USERINFO: Final = "/userinfo"


async def _alices_token(client: httpx.AsyncClient, scope: str) -> str:
    """Return an access token alice was issued, carrying ``scope``."""
    issued = await client.post(
        "/token",
        data={
            "grant_type": "password",
            "client_id": SERVICE_CLIENT_ID,
            "client_secret": SERVICE_CLIENT_SECRET,
            "username": USER_IDENTIFIER,
            "password": USER_PASSWORD,
            "scope": scope,
        },
    )
    assert issued.status_code == 200, issued.text

    return text_field(json_of(issued), "access_token")


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _read(scope: str = "openid profile email") -> httpx.Response:
    """Read the endpoint with a token of alice's carrying ``scope``."""
    async with serving(served_application(openid_kernel(USERINFO_ENV))) as client:
        return await client.get(USERINFO, headers=_bearer(await _alices_token(client, scope)))


# Section 5.3.1 — UserInfo Request


async def test_the_endpoint_answers_a_get_carrying_a_bearer_token() -> None:
    # "The UserInfo Endpoint MUST support the use of the HTTP GET and HTTP
    # POST methods"; "MUST accept Access Tokens as OAuth 2.0 Bearer Token
    # Usage."
    answered = await _read()

    assert answered.status_code == 200, answered.text


async def test_the_endpoint_answers_a_post_carrying_a_bearer_token() -> None:
    async with serving(served_application(openid_kernel(USERINFO_ENV))) as client:
        token = await _alices_token(client, "openid profile email")
        answered = await client.post(
            USERINFO,
            headers={**_bearer(token), "Content-Type": "application/x-www-form-urlencoded"},
            content=b"",
        )

    assert answered.status_code == 200, answered.text
    assert json_of(answered)["sub"] == USER_IDENTIFIER


async def test_a_token_carried_in_the_form_body_alone_is_not_read() -> None:
    # A deliberate deviation, recorded: RFC 6750 Section 2.2's form-encoded
    # body parameter is not read; the token goes in the Authorization header.
    async with serving(served_application(openid_kernel(USERINFO_ENV))) as client:
        token = await _alices_token(client, "openid profile email")
        answered = await client.post(USERINFO, data={"access_token": token})

    assert answered.status_code == 401
    assert text_field(json_of(answered), "error") == "invalid_token"


# Section 5.3.2 — Successful UserInfo Response


async def test_the_answer_is_a_json_object() -> None:
    # "The UserInfo Endpoint MUST return a content-type header to indicate
    # which format is being returned"; JSON here.
    answered = await _read()

    assert answered.headers["content-type"] == "application/json"
    assert isinstance(answered.json(), dict)


async def test_the_subject_is_always_answered() -> None:
    # "The sub (subject) Claim MUST always be returned in the UserInfo
    # Response."
    answered = await _read("openid")

    assert json_of(answered) == {"sub": USER_IDENTIFIER}


async def test_the_subject_answered_is_the_one_the_id_token_names() -> None:
    # "The sub Claim in the UserInfo Response MUST be verified to exactly
    # match the sub Claim in the ID Token" — a check the client makes, which
    # only a provider answering the same subject passes.
    async with serving(served_application(openid_kernel(USERINFO_ENV))) as client:
        issued = await signed_in(client)
        access_token = text_field(issued, "access_token")
        relying_party = await relying_party_of(client, ALGORITHM, access_token=access_token)

    badge = await relying_party.user_info.get_user_badge_from(access_token)
    assert badge.get_user_identifier() == claims_of(text_field(issued, "id_token"))["sub"]


# Section 5.4 — Requesting Claims using Scope Values


async def test_the_scopes_granted_reveal_their_claims() -> None:
    # "profile ... email ... This scope value requests access to the ...
    # Claims"; the claims the end-user has, and no others.
    answered = await _read("openid profile email")

    assert json_of(answered) == {
        "sub": USER_IDENTIFIER,
        "name": "Alice",
        "email": "alice@example.com",
        "email_verified": True,
    }


async def test_a_claim_of_a_scope_not_granted_is_not_revealed() -> None:
    answered = await _read("openid profile")

    assert "email" not in json_of(answered)


# Section 5.3.3 — UserInfo Error Response, as RFC 6750 Section 3 words it


async def test_a_request_carrying_no_token_is_refused_with_a_challenge() -> None:
    async with serving(served_application(openid_kernel(IDENTITY_PROVIDER_ENV))) as client:
        answered = await client.get(USERINFO)

    assert answered.status_code == 401
    assert answered.headers["www-authenticate"].startswith("Bearer ")
    assert text_field(json_of(answered), "error") == "invalid_token"


async def test_a_token_not_granted_openid_is_refused_as_insufficient() -> None:
    answered = await _read("profile email")

    assert answered.status_code == 403
    assert text_field(json_of(answered), "error") == "insufficient_scope"
    assert 'scope="openid"' in answered.headers["www-authenticate"]


async def test_a_token_naming_no_end_user_is_refused() -> None:
    # A client acting for itself carries openid, but nobody signed in.
    async with serving(served_application(openid_kernel(USERINFO_ENV))) as client:
        issued = await client.post(
            "/token",
            data={
                "grant_type": "client_credentials",
                "client_id": SERVICE_CLIENT_ID,
                "client_secret": SERVICE_CLIENT_SECRET,
                "scope": "openid",
            },
        )
        token = text_field(json_of(issued), "access_token")
        answered = await client.get(USERINFO, headers=_bearer(token))

    assert answered.status_code == 401
    assert text_field(json_of(answered), "error") == "invalid_token"
