"""Consent asked for rather than assumed, and the unhashed proof key.

Two branches of the authorization endpoint nothing else reaches: a listener
answering the browser itself — the consent page — and the refusal of a code
challenge sent unhashed by a client whose registration does not allow it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final
from urllib.parse import parse_qsl, urlsplit

import pytest
from fastapi import FastAPI
from xtr_security_http.firewall.firewall import Firewall

from tests.fixtures.oauth2_consent_app.config import USER_IDENTIFIER, USER_PASSWORD
from tests.fixtures.oauth2_consent_app.listeners import CONSENT_PAGE, GRANTED
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

if TYPE_CHECKING:
    from collections.abc import Mapping

    import httpx

pytestmark = pytest.mark.anyio

#: A proof key, within the length the standard allows.
VERIFIER: Final = "a-code-verifier-long-enough-for-the-standard"

#: The state the browser arrives with before anybody has consented.
ASKING: Final = "the-browser-just-arrived"

#: What a client is told when it sent the verifier unhashed and may not.
_NOT_ALLOWED: Final = "Plain code challenge method is not allowed for this client"


def _application() -> FastAPI:
    """Return the deployment whose listener shows a consent page."""
    return served_application(
        oauth2_kernel("tests.fixtures.oauth2_consent_app"),
        dependencies=[Firewall()],
    )


def _delivered(response: httpx.Response) -> Mapping[str, str]:
    """Return the parameters the authorization response was delivered in."""
    return dict(parse_qsl(urlsplit(response.headers["location"]).query))


async def _seed(client: httpx.AsyncClient, *, plain_pkce: bool = False) -> None:
    """Register a client that may drive both flows, with or without plain PKCE."""
    seeded = await client.post(
        SEED_PATH,
        params={"grant": "", "redirect_uri": REDIRECT_URI, "plain_pkce": plain_pkce},
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


async def _authorize(
    client: httpx.AsyncClient,
    state: str,
    challenge: str,
    method: str,
) -> httpx.Response:
    """Ask for a code as the established resource owner."""
    return await client.get(
        "/authorize",
        params={
            "response_type": "code",
            "client_id": CLIENT_ID,
            "redirect_uri": REDIRECT_URI,
            "state": state,
            "scope": SCOPE,
            "code_challenge": challenge,
            "code_challenge_method": method,
        },
        headers={"Authorization": f"Bearer {await _owner_token(client)}"},
    )


async def test_a_listener_may_answer_the_browser_itself() -> None:
    # The consent page: the deployment answers, and nothing is issued.
    async with serving(_application()) as client:
        await _seed(client)
        answered = await _authorize(client, ASKING, code_challenge_of(VERIFIER), "S256")

    assert answered.status_code == 200
    assert answered.text == CONSENT_PAGE
    assert "location" not in answered.headers


async def test_the_second_pass_is_approved_and_redirects_with_a_code() -> None:
    # Nothing was remembered between the two: the form posted the original
    # query back, so the same request reaches the same listener and this time
    # is approved.
    async with serving(_application()) as client:
        await _seed(client)
        answered = await _authorize(client, GRANTED, code_challenge_of(VERIFIER), "S256")

    assert answered.status_code == 302
    delivered = _delivered(answered)
    assert delivered["code"]
    assert delivered["state"] == GRANTED


async def test_an_unhashed_proof_key_is_refused_unless_the_client_may_send_one() -> None:
    # The unhashed method puts the verifier in the authorization request, where
    # every hop that sees the request sees it.
    async with serving(_application()) as client:
        await _seed(client, plain_pkce=False)
        answered = await _authorize(client, GRANTED, VERIFIER, "plain")

    assert answered.status_code == 400
    refused = json_of(answered)
    assert text_field(refused, "error") == "invalid_request"
    assert text_field(refused, "hint") == _NOT_ALLOWED


async def test_an_unhashed_proof_key_is_accepted_from_a_client_registered_for_one() -> None:
    # It stays available because a client on a platform without a hash cannot
    # do better — but only for a client whose registration says so.
    async with serving(_application()) as client:
        await _seed(client, plain_pkce=True)
        answered = await _authorize(client, GRANTED, VERIFIER, "plain")

    assert answered.status_code == 302
    assert _delivered(answered)["code"]


async def test_a_code_tied_to_an_unhashed_key_is_redeemed_with_the_verifier() -> None:
    async with serving(_application()) as client:
        await _seed(client, plain_pkce=True)
        answered = await _authorize(client, GRANTED, VERIFIER, "plain")
        redeemed = await client.post(
            "/token",
            data={
                "grant_type": "authorization_code",
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "redirect_uri": REDIRECT_URI,
                "code": _delivered(answered)["code"],
                "code_verifier": VERIFIER,
            },
        )

    assert redeemed.status_code == 200, redeemed.text
    assert text_field(json_of(redeemed), "access_token")
