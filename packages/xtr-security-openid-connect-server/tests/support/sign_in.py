"""The steps of a sign-in the conformance suite drives, as a client and a browser take them.

The resource owner is established on the authorization endpoint by an access
token the deployment minted with the password flow — the fixture's cheapest
signed-in end-user — and the code is redeemed as the public client the served
application seeds, with its proof key.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from tests.fixtures.openid_app.config import USER_IDENTIFIER, USER_PASSWORD
from tests.support.served import (
    CLIENT_ID,
    REDIRECT_URI,
    SCOPE,
    VERIFIER,
    code_challenge_of,
    json_of,
    redirected_with,
    text_field,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    import httpx

__all__ = [
    "NONCE",
    "STATE",
    "authorization_query",
    "authorize",
    "owner_token",
    "redeem",
    "signed_in",
]

#: What the client sends to tie the ID token to its request.
NONCE: Final = "n-0S6_WzA2Mj"

#: What the client sends to tie the answer to its request.
STATE: Final = "af0ifjsldkj"


async def owner_token(client: httpx.AsyncClient, scope: str = "read") -> str:
    """Return an access token the resource owner was issued, proving who is signed in."""
    issued = await client.post(
        "/token",
        data={
            "grant_type": "password",
            "client_id": CLIENT_ID,
            "username": USER_IDENTIFIER,
            "password": USER_PASSWORD,
            "scope": scope,
        },
    )
    assert issued.status_code == 200, issued.text

    return text_field(json_of(issued), "access_token")


def authorization_query(**extra: str) -> dict[str, str]:
    """Return an authentication request's parameters, with ``extra`` over them."""
    return {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPE,
        "state": STATE,
        "nonce": NONCE,
        "code_challenge": code_challenge_of(VERIFIER),
        "code_challenge_method": "S256",
        **extra,
    }


async def authorize(client: httpx.AsyncClient, **extra: str) -> httpx.Response:
    """Ask for a code as the signed-in resource owner, with ``extra`` parameters."""
    return await client.get(
        "/authorize",
        params=authorization_query(**extra),
        headers={"Authorization": f"Bearer {await owner_token(client)}"},
    )


async def redeem(
    client: httpx.AsyncClient,
    code: str,
    headers: Mapping[str, str] | None = None,
) -> httpx.Response:
    """Redeem ``code`` at the token endpoint, as the client it was issued to."""
    return await client.post(
        "/token",
        data={
            "grant_type": "authorization_code",
            "client_id": CLIENT_ID,
            "redirect_uri": REDIRECT_URI,
            "code": code,
            "code_verifier": VERIFIER,
        },
        headers=dict(headers or {}),
    )


async def signed_in(client: httpx.AsyncClient, **extra: str) -> Mapping[str, object]:
    """Drive a whole sign-in with ``extra`` parameters and return the token answer."""
    code = redirected_with(await authorize(client, **extra))["code"]
    answered = await redeem(client, code)
    assert answered.status_code == 200, answered.text

    return json_of(answered)
