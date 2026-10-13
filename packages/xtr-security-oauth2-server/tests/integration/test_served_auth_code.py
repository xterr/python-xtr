"""The browser redirect flow, served for real, proof key and all.

Consent is stateless, so the two halves of the flow are two ordinary requests:
the resource owner is established on ``/authorize`` and a listener approves,
then the client redeems the code it was redirected with.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final
from urllib.parse import parse_qsl, urlsplit

import httpx
import pytest
from fastapi import FastAPI
from xtr_dependency_injection import Injected
from xtr_security_http.firewall.firewall import Firewall

from tests.fixtures.oauth2_auth_code_app.config import USER_IDENTIFIER, USER_PASSWORD
from tests.fixtures.oauth2_auth_code_app.listeners import ASKED
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
)
from xtr_security_oauth2_server.manager.client_manager_interface import ClientManagerInterface

if TYPE_CHECKING:
    from collections.abc import Mapping

pytestmark = pytest.mark.anyio

#: A proof key, within the length the standard allows.
VERIFIER: Final = "a-code-verifier-long-enough-for-the-standard"

#: Another well-formed proof key, so that presenting the wrong one is refused
#: by the *comparison* rather than by the length check in front of it.
WRONG_VERIFIER: Final = "b-different-code-verifier-long-enough-for-the-standard"

#: Too short for the standard's 43 characters, so it never reaches the
#: comparison at all.
MALFORMED_VERIFIER: Final = "far-too-short-to-be-a-verifier"

#: What a client sends to tie the authorization request to that proof key.
CHALLENGE: Final = code_challenge_of(VERIFIER)

#: What ties the redirect back to the browser that started the flow.
STATE: Final = "the-opaque-state"

PUBLIC_CLIENT_ID: Final = "a-public-client"

#: Where the served application deactivates a client, as an administration
#: screen or the update-client command would.
DEACTIVATE_PATH: Final = "/deactivate-client"


def _application() -> FastAPI:
    """Return the served application of the redirect-flow deployment.

    The firewall goes on the application, not on the routes this package
    contributes: they carry no dependency of their own, so an unbound
    ``Firewall()`` here is what establishes the resource owner before the
    authorization endpoint asks anybody to approve. Which requests it claims
    is the firewall pattern's to decide, which is why the token endpoint stays
    outside it.
    """
    return served_application(
        oauth2_kernel("tests.fixtures.oauth2_auth_code_app"),
        dependencies=[Firewall()],
    )


def _mount_deactivation(app: FastAPI) -> None:
    """Add the route that deactivates a client through the client manager."""

    @app.post(DEACTIVATE_PATH)
    async def deactivate_client(
        clients: Injected[ClientManagerInterface],
        *,
        identifier: str,
    ) -> dict[str, str]:
        registered = await clients.find(identifier)
        assert registered is not None
        await clients.save(registered.set_active(False))

        return {"client_id": identifier}


def _administered_application() -> FastAPI:
    """Return the redirect-flow deployment, with a way to deactivate a client."""
    return served_application(
        oauth2_kernel("tests.fixtures.oauth2_auth_code_app"),
        _mount_deactivation,
        dependencies=[Firewall()],
    )


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


def _redirect_params(response: httpx.Response) -> Mapping[str, str]:
    """Return the parameters the authorization response was delivered in."""
    return dict(parse_qsl(urlsplit(response.headers["location"]).query))


async def _authorize(
    client: httpx.AsyncClient,
    token: str,
    challenge: str | None = CHALLENGE,
    client_id: str = CLIENT_ID,
) -> httpx.Response:
    """Ask for an authorization code as the established resource owner."""
    query = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "state": STATE,
        "scope": SCOPE,
    }
    if challenge is not None:
        query["code_challenge"] = challenge
        query["code_challenge_method"] = "S256"

    return await client.get(
        "/authorize",
        params=query,
        headers={"Authorization": f"Bearer {token}"},
    )


async def _seed(client: httpx.AsyncClient) -> None:
    """Register a confidential client that may drive both flows."""
    seeded = await client.post(
        SEED_PATH,
        params={"grant": "", "redirect_uri": REDIRECT_URI},
    )
    # A seed that quietly failed would surface far away, as a client that
    # cannot authenticate.
    assert seeded.status_code == 200, seeded.text


async def _seed_public_client(client: httpx.AsyncClient) -> None:
    """Register a client holding no secret, beside the confidential one."""
    seeded = await client.post(
        SEED_PATH,
        params={
            "identifier": PUBLIC_CLIENT_ID,
            "secret": "",
            "grant": "",
            "redirect_uri": REDIRECT_URI,
        },
    )
    assert seeded.status_code == 200, seeded.text


async def _deactivate(client: httpx.AsyncClient, identifier: str) -> None:
    """Deactivate the client registered as ``identifier``."""
    deactivated = await client.post(DEACTIVATE_PATH, params={"identifier": identifier})
    assert deactivated.status_code == 200, deactivated.text


async def _code(client: httpx.AsyncClient) -> str:
    """Drive the first half of the flow and return the code it issued."""
    await _seed(client)
    answered = await _authorize(client, await _owner_token(client))
    delivered = _redirect_params(answered)
    # An authorization response that carried a refusal instead of a code
    # should say so here, not as a missing key.
    assert "code" in delivered, f"{answered.status_code}: {delivered}"

    return delivered["code"]


async def test_an_approved_request_redirects_with_a_code_and_the_state() -> None:
    ASKED.clear()

    async with serving(_application()) as client:
        await _seed(client)
        answered = await _authorize(client, await _owner_token(client))

    assert answered.status_code == 302
    delivered = _redirect_params(answered)
    assert delivered["code"]
    # What ties the redirect back to the browser that started the flow.
    assert delivered["state"] == STATE
    assert answered.headers["location"].startswith(REDIRECT_URI)


async def test_the_deployment_is_the_one_asked_to_approve() -> None:
    ASKED.clear()

    async with serving(_application()) as client:
        await _seed(client)
        _ = await _authorize(client, await _owner_token(client))

    assert ASKED == [CLIENT_ID]


async def test_a_code_is_redeemed_for_a_token_pair() -> None:
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
    issued = json_of(answered)
    assert text_field(issued, "access_token")
    assert text_field(issued, "refresh_token")


async def test_a_code_cannot_be_redeemed_twice() -> None:
    # A code that kept working would let whoever saw it once use it again.
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
        answered = await client.post("/token", data=form)

    assert first.status_code == 200
    assert answered.status_code == 400
    assert text_field(json_of(answered), "error") == "invalid_grant"


async def test_a_code_is_refused_without_the_proof_key_it_was_tied_to() -> None:
    # The whole point of the proof key: the challenge travelled where every hop
    # could see it, and only the holder of the verifier may redeem the code.
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


async def test_a_proof_key_the_standard_would_not_accept_is_refused_before_comparison() -> None:
    # Checked for shape first, so a verifier that could never be one is a
    # malformed request rather than a failed proof.
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
                "code_verifier": MALFORMED_VERIFIER,
            },
        )

    assert answered.status_code == 400
    assert text_field(json_of(answered), "error") == "invalid_request"


async def test_a_public_client_must_commit_to_a_proof_key() -> None:
    # A client holding no secret has nothing else to prove it is the one the
    # code was issued to.
    async with serving(_application()) as client:
        # The confidential client first: it is what the password flow
        # establishes the resource owner with.
        await _seed(client)
        _ = await client.post(
            SEED_PATH,
            params={
                "identifier": PUBLIC_CLIENT_ID,
                "secret": "",
                "grant": "",
                "redirect_uri": REDIRECT_URI,
            },
        )
        owner = await _owner_token(client)
        answered = await _authorize(
            client,
            owner,
            challenge=None,
            client_id=PUBLIC_CLIENT_ID,
        )

    # Answered as a plain document rather than delivered to the redirect URI:
    # the requirement is settled while the request is still being read, before
    # any redirect target has been established as one worth trusting.
    assert answered.status_code == 400
    assert text_field(json_of(answered), "error") == "invalid_request"


async def test_a_deactivated_public_client_is_refused_at_the_authorization_endpoint() -> None:
    # A client holding no secret is never asked to prove one, so nothing but
    # the lookup stands between a deactivated one and a code.
    async with serving(_administered_application()) as client:
        await _seed(client)
        await _seed_public_client(client)
        owner = await _owner_token(client)
        await _deactivate(client, PUBLIC_CLIENT_ID)
        answered = await _authorize(client, owner, client_id=PUBLIC_CLIENT_ID)

    assert answered.status_code == 401
    assert text_field(json_of(answered), "error") == "invalid_client"


async def test_a_deactivated_public_client_cannot_spend_its_refresh_token() -> None:
    # The tokens it already holds stop being redeemable with it.
    async with serving(_administered_application()) as client:
        await _seed(client)
        await _seed_public_client(client)
        authorized = await _authorize(
            client, await _owner_token(client), client_id=PUBLIC_CLIENT_ID
        )
        issued = json_of(
            await client.post(
                "/token",
                data={
                    "grant_type": "authorization_code",
                    "client_id": PUBLIC_CLIENT_ID,
                    "redirect_uri": REDIRECT_URI,
                    "code": _redirect_params(authorized)["code"],
                    "code_verifier": VERIFIER,
                },
            ),
        )
        await _deactivate(client, PUBLIC_CLIENT_ID)
        answered = await client.post(
            "/token",
            data={
                "grant_type": "refresh_token",
                "client_id": PUBLIC_CLIENT_ID,
                "refresh_token": text_field(issued, "refresh_token"),
            },
        )

    assert answered.status_code == 401
    assert text_field(json_of(answered), "error") == "invalid_client"


async def test_nobody_established_means_nobody_to_ask() -> None:
    async with serving(_application()) as client:
        await _seed(client)
        answered = await client.get(
            "/authorize",
            params={
                "response_type": "code",
                "client_id": CLIENT_ID,
                "redirect_uri": REDIRECT_URI,
                "state": STATE,
            },
        )

    assert answered.status_code == 401
