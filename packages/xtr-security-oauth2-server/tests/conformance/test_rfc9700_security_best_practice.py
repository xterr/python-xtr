"""RFC 9700 — Best Current Practice for OAuth 2.0 Security.

Only the requirements on an authorization server are here; the ones addressed
to clients are a client's to meet. Section 2.1's countermeasures and the
section 4 attacks they answer are covered; the defence against mix-up attacks
(section 4.4) is the issuer parameter of RFC 9207, which this package does not
issue — out of scope by the plan, and listed as not covered in ``README.md``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final
from urllib.parse import parse_qsl, urlsplit

import pytest
from fastapi import FastAPI

from tests.fixtures.oauth2_auth_code_app.config import USER_IDENTIFIER, USER_PASSWORD
from tests.support.served import (
    CLIENT_ID,
    CLIENT_SECRET,
    REDIRECT_URI,
    SCOPE,
    SEED_PATH,
    code_challenge_of,
    json_of,
    oauth2_kernel,
    served_application,
    serving,
    text_field,
    text_fields,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    import httpx

pytestmark = pytest.mark.anyio

VERIFIER: Final = "a-code-verifier-long-enough-for-the-standard"
CHALLENGE: Final = code_challenge_of(VERIFIER)

#: Another well-formed proof key, so a wrong one is refused by the comparison
#: rather than by the length check in front of it.
WRONG_VERIFIER: Final = "b-different-code-verifier-long-enough-for-the-standard"

STATE: Final = "the-opaque-state"

#: A loopback redirect of the kind RFC 8252 section 7.3 is about: the port is
#: whichever one a native application managed to listen on.
LOOPBACK_REGISTERED: Final = "http://127.0.0.1:1234/callback"
LOOPBACK_ANOTHER_PORT: Final = "http://127.0.0.1:56789/callback"
LOOPBACK_ANOTHER_PATH: Final = "http://127.0.0.1:1234/elsewhere"

#: What ``localhost`` resolves to is the host file's business, so a redirect
#: naming it is not the loopback literal the exception is written for.
LOOPBACK_BY_NAME: Final = "http://localhost:1234/callback"

PUBLIC_CLIENT_ID: Final = "a-public-client"


def _application() -> FastAPI:
    """Return a deployment running the redirect flow, proof key required."""
    return served_application(
        oauth2_kernel("tests.fixtures.oauth2_auth_code_app"),
    )


def _rotating_application() -> FastAPI:
    """Return a deployment that issues refresh tokens and rotates them."""
    return served_application(oauth2_kernel("tests.fixtures.oauth2_password_app"))


async def _seed(client: httpx.AsyncClient, **params: str) -> None:
    """Register a client that may drive every flow."""
    seeded = await client.post(
        SEED_PATH,
        params={"grant": "", "redirect_uri": REDIRECT_URI, **params},
    )
    assert seeded.status_code == 200, seeded.text


async def _owner_token(client: httpx.AsyncClient) -> str:
    """Establish the resource owner, and return the token that proves them."""
    issued = json_of(
        await client.post(
            "/token",
            data={
                "grant_type": "password",
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "username": USER_IDENTIFIER,
                "password": USER_PASSWORD,
                "scope": SCOPE,
            },
        ),
    )

    return text_field(issued, "access_token")


def _delivered(response: httpx.Response) -> Mapping[str, str]:
    """Return the parameters an authorization response was delivered in."""
    return dict(parse_qsl(urlsplit(response.headers["location"]).query))


async def _authorize(
    client: httpx.AsyncClient,
    token: str,
    client_id: str = CLIENT_ID,
    **extra: str,
) -> httpx.Response:
    """Ask for an authorization code, naming whatever the caller names."""
    query = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "state": STATE,
        "scope": SCOPE,
        **extra,
    }

    return await client.get(
        "/authorize",
        params=query,
        headers={"Authorization": f"Bearer {token}"},
    )


async def _code(client: httpx.AsyncClient, **extra: str) -> str:
    """Drive the first half of the flow and return the code it issued."""
    await _seed(client)
    answered = await _authorize(
        client,
        await _owner_token(client),
        code_challenge=CHALLENGE,
        code_challenge_method="S256",
        **extra,
    )
    delivered = _delivered(answered)
    assert "code" in delivered, f"{answered.status_code}: {delivered}"

    return delivered["code"]


async def _refresh_token(client: httpx.AsyncClient, scope: str = SCOPE) -> str:
    """Return a refresh token the resource owner's own credentials earned.

    The client is registered for both scopes and asks for ``scope``, so that a
    scope it is *registered* for can still be one the resource owner never
    consented to.
    """
    seeded = await client.post(SEED_PATH, params={"grant": "", "scope": "read write"})
    assert seeded.status_code == 200, seeded.text
    issued = json_of(
        await client.post(
            "/token",
            data={
                "grant_type": "password",
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "username": USER_IDENTIFIER,
                "password": USER_PASSWORD,
                "scope": scope,
            },
        ),
    )

    return text_field(issued, "refresh_token")


# Section 2.1 / 4.1.3 — Exact redirection URI matching


async def test_a_redirect_uri_is_matched_as_the_very_same_text() -> None:
    # "When comparing client redirection URIs against pre-registered URIs,
    # authorization servers MUST utilize exact string matching" (section 2.1),
    # and section 4.1.3: "the authorization server MUST ensure that the two
    # URIs are equal; see Section 6.2.1 of [RFC3986], Simple String
    # Comparison". A registered prefix is therefore not a match.
    async with serving(_application()) as client:
        await _seed(client)
        owner = await _owner_token(client)
        for named in (
            f"{REDIRECT_URI}/deeper",
            f"{REDIRECT_URI}?extra=1",
            "https://client.test.attacker.test/callback",
            "https://CLIENT.test/callback",
        ):
            answered = await _authorize(client, owner, redirect_uri=named)

            assert answered.status_code == 401, named
            assert "location" not in answered.headers


async def test_a_loopback_redirect_may_arrive_on_another_port() -> None:
    # "The only exception is native apps using a localhost URI: In this case,
    # the authorization server MUST allow variable port numbers as described in
    # Section 7.3 of [RFC8252]" (section 4.1.3).
    async with serving(_application()) as client:
        await _seed(client)
        await _seed(client, identifier="a-native-client", redirect_uri=LOOPBACK_REGISTERED)
        answered = await _authorize(
            client,
            await _owner_token(client),
            client_id="a-native-client",
            redirect_uri=LOOPBACK_ANOTHER_PORT,
            code_challenge=CHALLENGE,
            code_challenge_method="S256",
        )

    assert answered.status_code == 302
    assert _delivered(answered)["code"]
    assert answered.headers["location"].startswith(LOOPBACK_ANOTHER_PORT)


async def test_the_exception_is_about_the_port_and_nothing_else() -> None:
    # RFC 8252 section 7.3 varies the port only, so the path still has to
    # match exactly (section 4.1.3).
    async with serving(_application()) as client:
        await _seed(client)
        await _seed(client, identifier="a-native-client", redirect_uri=LOOPBACK_REGISTERED)
        answered = await _authorize(
            client,
            await _owner_token(client),
            client_id="a-native-client",
            redirect_uri=LOOPBACK_ANOTHER_PATH,
            code_challenge=CHALLENGE,
            code_challenge_method="S256",
        )

    assert answered.status_code == 401


async def test_a_redirect_naming_the_loopback_by_name_is_not_the_exception() -> None:
    # RFC 8252 section 7.3: "the loopback IP literal rather than localhost",
    # because what the name resolves to is not the authorization server's to
    # know. So a request naming it is matched exactly, like any other.
    async with serving(_application()) as client:
        await _seed(client)
        await _seed(client, identifier="a-native-client", redirect_uri=LOOPBACK_BY_NAME)
        answered = await _authorize(
            client,
            await _owner_token(client),
            client_id="a-native-client",
            redirect_uri="http://localhost:56789/callback",
            code_challenge=CHALLENGE,
            code_challenge_method="S256",
        )

    assert answered.status_code == 401


# Section 2.1 / 4.11 — No open redirector


async def test_a_refusal_never_forwards_the_browser_somewhere_the_request_chose() -> None:
    # "Clients and authorization servers MUST NOT expose URLs that forward the
    # user's browser to arbitrary URIs obtained from a query parameter (open
    # redirectors)" (section 2.1). The one query parameter here that is a URL
    # is ``redirect_uri``, and a refusal about it is answered as a document.
    async with serving(_application()) as client:
        await _seed(client)
        answered = await _authorize(
            client,
            await _owner_token(client),
            redirect_uri="https://attacker.test/collect",
        )

    assert answered.status_code == 401
    assert "location" not in answered.headers
    assert "attacker.test" not in answered.text


async def test_a_refusal_the_client_is_entitled_to_goes_only_to_a_registered_uri() -> None:
    # The other half: once the redirect URI has been established as one the
    # client registered, a refusal may be delivered there (RFC 6749 section
    # 4.1.2.1), and nowhere else.
    async with serving(_application()) as client:
        await _seed(client)
        answered = await _authorize(
            client,
            await _owner_token(client),
            scope="nothing-registered",
            code_challenge=CHALLENGE,
            code_challenge_method="S256",
        )

    assert answered.status_code == 302
    assert answered.headers["location"].startswith(REDIRECT_URI)
    delivered = _delivered(answered)
    assert delivered["error"] == "invalid_scope"
    # The state travels with the refusal, so the browser that started the flow
    # is the one that can make sense of it.
    assert delivered["state"] == STATE


# Section 2.1.1 — Proof key support and enforcement


async def test_this_server_supports_the_proof_key_mechanism() -> None:
    # "Authorization servers MUST support PKCE [RFC7636]" (section 2.1.1).
    async with serving(_application()) as client:
        code = await _code(client)
        answered = await client.post(
            "/token",
            data={
                "grant_type": "authorization_code",
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "redirect_uri": REDIRECT_URI,
                "code": code,
                "code_verifier": VERIFIER,
            },
        )

    assert answered.status_code == 200


async def test_the_support_can_be_detected_from_the_published_description() -> None:
    # "Authorization servers MUST provide a way to detect their support for
    # PKCE. It is RECOMMENDED for authorization servers to publish the element
    # code_challenge_methods_supported in their Authorization Server Metadata"
    # (section 2.1.1).
    async with serving(_application()) as client:
        published = json_of(await client.get("/.well-known/oauth-authorization-server"))

    assert "S256" in text_fields(published, "code_challenge_methods_supported")


async def test_a_challenge_that_was_sent_is_enforced_at_the_token_endpoint() -> None:
    # "If a client sends a valid PKCE code_challenge parameter in the
    # authorization request, the authorization server MUST enforce the correct
    # usage of code_verifier at the token endpoint" (section 2.1.1).
    async with serving(_application()) as client:
        code = await _code(client)
        answered = await client.post(
            "/token",
            data={
                "grant_type": "authorization_code",
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "redirect_uri": REDIRECT_URI,
                "code": code,
                "code_verifier": WRONG_VERIFIER,
            },
        )

    assert answered.status_code == 400
    assert text_field(json_of(answered), "error") == "invalid_grant"


async def test_a_public_client_is_made_to_commit_to_a_proof_key() -> None:
    # "Public clients MUST use PKCE [RFC7636] to this end" (section 2.1.1),
    # which an authorization server is the one that can insist on.
    async with serving(_application()) as client:
        await _seed(client)
        await _seed(client, identifier=PUBLIC_CLIENT_ID, secret="")
        answered = await _authorize(
            client,
            await _owner_token(client),
            client_id=PUBLIC_CLIENT_ID,
        )

    assert answered.status_code == 400
    assert text_field(json_of(answered), "error") == "invalid_request"


# Section 4.8.2 — PKCE downgrade


async def test_a_verifier_arriving_for_a_code_tied_to_no_challenge_is_refused() -> None:
    # "to prevent PKCE downgrade attacks, the authorization server MUST ensure
    # that if there was no code_challenge in the authorization request, a
    # request to the token endpoint containing a code_verifier is rejected"
    # (section 4.8.2), and section 2.1.1 states the same requirement.
    async with serving(_application()) as client:
        await _seed(client)
        answered = await _authorize(client, await _owner_token(client))
        code = _delivered(answered)["code"]
        redeemed = await client.post(
            "/token",
            data={
                "grant_type": "authorization_code",
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "redirect_uri": REDIRECT_URI,
                "code": code,
                "code_verifier": VERIFIER,
            },
        )

    assert redeemed.status_code == 400
    assert text_field(json_of(redeemed), "error") == "invalid_request"


# Section 4.5 — Authorization code injection


async def test_a_code_is_good_for_exactly_one_exchange() -> None:
    # Section 4.5's injection attack rests on a code being usable by whoever
    # presents it; single use is what makes a stolen code worth nothing once
    # the legitimate client has spent it (RFC 6749 section 4.1.2).
    async with serving(_application()) as client:
        code = await _code(client)
        form = {
            "grant_type": "authorization_code",
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "redirect_uri": REDIRECT_URI,
            "code": code,
            "code_verifier": VERIFIER,
        }
        first = await client.post("/token", data=form)
        again = await client.post("/token", data=form)

    assert first.status_code == 200
    assert again.status_code == 400
    assert "access_token" not in json_of(again)


async def test_a_stolen_code_is_worth_nothing_without_the_proof_key() -> None:
    # "Public clients MUST use PKCE ... the PKCE challenge or OpenID Connect
    # nonce MUST be transaction-specific and securely bound to the client and
    # the user agent in which the transaction was started" (section 2.1.1):
    # whoever intercepted the code holds the challenge, not the verifier.
    async with serving(_application()) as client:
        code = await _code(client)
        answered = await client.post(
            "/token",
            data={
                "grant_type": "authorization_code",
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "redirect_uri": REDIRECT_URI,
                "code": code,
                "code_verifier": CHALLENGE,
            },
        )

    assert answered.status_code == 400
    assert "access_token" not in json_of(answered)


# Section 2.2.2 / 4.14.2 — Refresh token protection


async def test_a_refresh_hands_back_a_new_refresh_token() -> None:
    # "Refresh token rotation: the authorization server issues a new refresh
    # token with every access token refresh response" (section 4.14.2), which
    # section 2.2.2 requires of refresh tokens for public clients.
    async with serving(_rotating_application()) as client:
        refresh = await _refresh_token(client)
        answered = await client.post(
            "/token",
            data={
                "grant_type": "refresh_token",
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "refresh_token": refresh,
            },
        )

    issued = json_of(answered)
    assert answered.status_code == 200
    assert text_field(issued, "refresh_token") != refresh


async def test_the_refresh_token_that_was_spent_stops_working() -> None:
    # "The previous refresh token is invalidated ... If a refresh token is
    # compromised and subsequently used by both the attacker and the
    # legitimate client, one of them will present an invalidated refresh
    # token, which will inform the authorization server of the breach"
    # (section 4.14.2).
    async with serving(_rotating_application()) as client:
        refresh = await _refresh_token(client)
        form = {
            "grant_type": "refresh_token",
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "refresh_token": refresh,
        }
        rotated = await client.post("/token", data=form)
        replayed = await client.post("/token", data=form)

    assert rotated.status_code == 200
    assert replayed.status_code == 400
    assert text_field(json_of(replayed), "error") == "invalid_grant"


async def test_a_refresh_token_stays_bound_to_what_was_consented_to() -> None:
    # "If refresh tokens are issued, those refresh tokens MUST be bound to the
    # scope and resource servers as consented by the resource owner. This is to
    # prevent privilege escalation by the legitimate client" (section 4.14.2).
    # The client *is* registered for the wider scope, so what refuses the
    # request is the binding to what was granted and nothing else.
    async with serving(_rotating_application()) as client:
        refresh = await _refresh_token(client, "read")
        answered = await client.post(
            "/token",
            data={
                "grant_type": "refresh_token",
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "refresh_token": refresh,
                "scope": "write",
            },
        )

    assert answered.status_code == 400
    assert text_field(json_of(answered), "error") == "invalid_scope"


# Section 2.5 — Client authentication


async def test_a_client_holding_a_secret_is_made_to_present_it() -> None:
    # "Authorization servers SHOULD enforce client authentication if it is
    # feasible" (section 2.5): a client registered with a secret may do nothing
    # without it.
    async with serving(_application()) as client:
        await _seed(client)
        answered = await client.post(
            "/token",
            data={
                "grant_type": "client_credentials",
                "client_id": CLIENT_ID,
                "client_secret": "the-wrong-secret",
            },
        )

    assert answered.status_code == 401
    assert text_field(json_of(answered), "error") == "invalid_client"
