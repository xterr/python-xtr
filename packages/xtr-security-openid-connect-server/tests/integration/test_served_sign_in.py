"""A sign-in served for real: the provider's flow and answer, wired by its bundle.

The fixture deployment configures the authorization server only; the
provider's bundle puts its flow, its answer and the ``openid`` scope in place.
Every answer here is what a client would receive over the wire.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

import pytest
from joserfc import jwt

from tests.fixtures.openid_app.config import (
    ALGORITHM,
    ED448_ENV,
    ED25519_ENV,
    ID_TOKEN_TTL,
    OPEN_PROOF_KEY_ENV,
    SHORT_ID_TOKEN_ENV,
    USER_IDENTIFIER,
    USER_PASSWORD,
)
from tests.support.served import (
    CLIENT_ID,
    REDIRECT_URI,
    SCOPE,
    VERIFIER,
    claims_of,
    code_challenge_of,
    header_of,
    json_of,
    openid_kernel,
    redirected_with,
    served_application,
    serving,
    text_field,
)
from tests.support.signing import EDDSA_DEPRECATION, ISSUER, signing_key
from xtr_security_openid_connect_server.token_hash import token_hash

if TYPE_CHECKING:
    from collections.abc import Mapping

    import httpx

pytestmark = pytest.mark.anyio

NONCE: Final = "n-0S6_WzA2Mj"
STATE: Final = "the-opaque-state"


async def _owner_token(client: httpx.AsyncClient) -> str:
    """Establish the resource owner, and return the token that proves them."""
    issued = await client.post(
        "/token",
        data={
            "grant_type": "password",
            "client_id": CLIENT_ID,
            "username": USER_IDENTIFIER,
            "password": USER_PASSWORD,
            "scope": "read",
        },
    )
    assert issued.status_code == 200, issued.text

    return text_field(json_of(issued), "access_token")


async def _authorize(client: httpx.AsyncClient, *, proof_key: bool = True) -> httpx.Response:
    """Ask for a code as the signed-in resource owner, with or without a proof key."""
    query = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "state": STATE,
        "scope": SCOPE,
        "nonce": NONCE,
    }
    if proof_key:
        query["code_challenge"] = code_challenge_of(VERIFIER)
        query["code_challenge_method"] = "S256"

    return await client.get(
        "/authorize",
        params=query,
        headers={"Authorization": f"Bearer {await _owner_token(client)}"},
    )


async def _signed_in(client: httpx.AsyncClient, *, proof_key: bool = True) -> Mapping[str, object]:
    """Drive the whole sign-in and return the token answer it ended in."""
    code = redirected_with(await _authorize(client, proof_key=proof_key))["code"]
    form = {
        "grant_type": "authorization_code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "code": code,
    }
    if proof_key:
        form["code_verifier"] = VERIFIER
    answered = await client.post("/token", data=form)
    assert answered.status_code == 200, answered.text

    return json_of(answered)


async def _sign_in(env: str = "test", *, proof_key: bool = True) -> Mapping[str, object]:
    """Serve the deployment in ``env`` and sign in once."""
    async with serving(served_application(openid_kernel(env))) as client:
        return await _signed_in(client, proof_key=proof_key)


async def test_a_sign_in_is_answered_with_an_id_token_for_the_user() -> None:
    issued = await _sign_in()

    claims = claims_of(text_field(issued, "id_token"))
    assert (claims["iss"], claims["sub"], claims["aud"], claims["nonce"]) == (
        ISSUER,
        USER_IDENTIFIER,
        CLIENT_ID,
        NONCE,
    )


async def test_the_id_token_verifies_against_the_servers_own_key() -> None:
    issued = await _sign_in()

    # Raises unless the signature verifies with the key the server signs with.
    verified = jwt.decode(text_field(issued, "id_token"), signing_key(ALGORITHM))

    assert verified.claims["sub"] == USER_IDENTIFIER


async def test_the_id_token_is_signed_with_the_algorithm_the_server_is_configured_with() -> None:
    issued = await _sign_in()

    assert header_of(text_field(issued, "id_token"))["alg"] == ALGORITHM


async def test_the_id_token_hashes_the_access_token_issued_beside_it() -> None:
    issued = await _sign_in()

    at_hash = claims_of(text_field(issued, "id_token"))["at_hash"]
    assert at_hash == token_hash(text_field(issued, "access_token"), ALGORITHM)


@pytest.mark.filterwarnings(EDDSA_DEPRECATION)
@pytest.mark.parametrize(("env", "curve"), [(ED25519_ENV, "Ed25519"), (ED448_ENV, "Ed448")])
async def test_an_eddsa_id_token_hashes_the_access_token_as_its_keys_curve_says(
    env: str,
    curve: str,
) -> None:
    issued = await _sign_in(env)

    at_hash = claims_of(text_field(issued, "id_token"))["at_hash"]
    assert at_hash == token_hash(text_field(issued, "access_token"), "EdDSA", curve)


async def test_a_sign_in_proving_no_credential_states_no_sign_in_time() -> None:
    # The resource owner is established by an access token, which proves no
    # credential of theirs, so nothing says when they signed in.
    issued = await _sign_in()

    assert "auth_time" not in claims_of(text_field(issued, "id_token"))


async def test_an_id_token_expires_with_its_access_token_by_default() -> None:
    issued = await _sign_in()

    id_token = claims_of(text_field(issued, "id_token"))
    assert id_token["exp"] == claims_of(text_field(issued, "access_token"))["exp"]


async def test_an_id_token_lasts_as_long_as_the_deployment_set() -> None:
    issued = await _sign_in(SHORT_ID_TOKEN_ENV)

    claims = claims_of(text_field(issued, "id_token"))
    exp, iat = claims["exp"], claims["iat"]
    assert isinstance(exp, int)
    assert isinstance(iat, int)
    assert exp - iat == int(ID_TOKEN_TTL.total_seconds())


async def test_a_public_client_must_commit_to_a_proof_key_where_the_deployment_requires_one() -> (
    None
):
    async with serving(served_application(openid_kernel())) as client:
        answered = await _authorize(client, proof_key=False)

    assert answered.status_code == 400
    assert text_field(json_of(answered), "error") == "invalid_request"


async def test_a_public_client_signs_in_with_no_proof_key_where_the_deployment_requires_none() -> (
    None
):
    issued = await _sign_in(OPEN_PROOF_KEY_ENV, proof_key=False)

    assert text_field(issued, "id_token")
