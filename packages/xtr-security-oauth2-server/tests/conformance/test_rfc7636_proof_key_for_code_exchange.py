"""RFC 7636 — Proof Key for Code Exchange by OAuth Public Clients.

The derivation is fixed by the standard down to the byte, so Appendix B's
vector is checked against the verifier this package ships rather than through a
served request. Everything the standard says about what a client receives is
driven through a served application.
"""

from __future__ import annotations

import base64
import hashlib
from typing import TYPE_CHECKING, Final
from urllib.parse import parse_qsl, urlsplit

import pytest
from fastapi import FastAPI
from xtr_security_oauth2_server_core.code_challenge_verifiers.plain_verifier import PlainVerifier
from xtr_security_oauth2_server_core.code_challenge_verifiers.s256_verifier import S256Verifier

from tests.fixtures.oauth2_auth_code_app.config import USER_IDENTIFIER, USER_PASSWORD
from tests.support.served import (
    CLIENT_ID,
    CLIENT_SECRET,
    REDIRECT_URI,
    SCOPE,
    SEED_PATH,
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

#: Appendix B's octet sequence, as the standard writes it.
APPENDIX_B_OCTETS: Final = bytes(
    (
        116, 24, 223, 180, 151, 153, 224, 37, 79, 250, 96, 125, 216, 173,
        187, 186, 22, 212, 37, 77, 105, 214, 191, 240, 91, 88, 5, 88, 83,
        132, 141, 121,
    ),
)  # fmt: skip

#: Appendix B's code verifier: that sequence encoded as base64url.
APPENDIX_B_VERIFIER: Final = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"

#: The SHA-256 digest Appendix B says the verifier hashes to.
APPENDIX_B_DIGEST: Final = bytes(
    (
        19, 211, 30, 150, 26, 26, 216, 236, 47, 22, 177, 12, 76, 152, 46,
        8, 118, 168, 120, 173, 109, 241, 68, 86, 110, 225, 137, 74, 203,
        112, 249, 195,
    ),
)  # fmt: skip

#: Appendix B's code challenge: that digest encoded as base64url.
APPENDIX_B_CHALLENGE: Final = "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"

#: A verifier that is also a well-formed challenge, for the unhashed method:
#: the two are compared directly, so the one value has to satisfy both shapes.
PLAIN_VERIFIER: Final = "a-verifier-that-is-also-its-own-challenge-01"

#: Forty-two characters — one short of the shortest the standard allows.
TOO_SHORT: Final = "a" * 42

#: One hundred and twenty-nine — one more than the longest.
TOO_LONG: Final = "a" * 129

#: Inside the length, outside the character set the standard allows.
WRONG_CHARACTERS: Final = ("a" * 42) + "!"

STATE: Final = "the-opaque-state"

PUBLIC_CLIENT_ID: Final = "a-public-client"


def _application() -> FastAPI:
    """Return a deployment running the redirect flow, proof key required."""
    return served_application(
        oauth2_kernel("tests.fixtures.oauth2_auth_code_app"),
    )


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
    answered = await _authorize(client, await _owner_token(client), **extra)
    delivered = _delivered(answered)
    assert "code" in delivered, f"{answered.status_code}: {delivered}"

    return delivered["code"]


async def _redeem(client: httpx.AsyncClient, code: str, **extra: str) -> httpx.Response:
    """Exchange ``code``, naming whatever the caller names."""
    form = {
        "grant_type": "authorization_code",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "code": code,
        **extra,
    }

    return await client.post("/token", data=form)


# Appendix B — Example for the S256 code_challenge_method


def test_the_standards_own_example_verifier_is_the_encoded_octets() -> None:
    # Appendix B: "Encoding this octet sequence as base64url provides the value
    # of the code_verifier".
    encoded = base64.urlsafe_b64encode(APPENDIX_B_OCTETS).rstrip(b"=").decode("ascii")

    assert encoded == APPENDIX_B_VERIFIER


def test_the_standards_own_example_digest_is_the_hash_of_that_verifier() -> None:
    # Appendix B: "The code_verifier is then hashed via the SHA256 hash
    # function to produce [the digest]".
    assert hashlib.sha256(APPENDIX_B_VERIFIER.encode("ascii")).digest() == APPENDIX_B_DIGEST


def test_the_standards_own_example_challenge_verifies() -> None:
    # Appendix B: verifier ``dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk``
    # against challenge ``E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM``.
    assert S256Verifier().verify_code_challenge(APPENDIX_B_VERIFIER, APPENDIX_B_CHALLENGE)


def test_another_verifier_does_not_satisfy_that_challenge() -> None:
    # The same vector read the other way: the comparison is of the derived
    # value, not of anything the request chose (section 4.6).
    assert not S256Verifier().verify_code_challenge(PLAIN_VERIFIER, APPENDIX_B_CHALLENGE)


# Section 4.2 — Client Creates the Code Challenge


def test_the_hashed_method_is_the_digest_encoded_without_padding() -> None:
    # Section 4.2 writes the hashed transformation as the base64url encoding of
    # the SHA-256 digest of the verifier, and BASE64URL in the standards it
    # builds on carries no padding.
    digest = hashlib.sha256(APPENDIX_B_VERIFIER.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")

    assert "=" not in challenge
    assert S256Verifier().verify_code_challenge(APPENDIX_B_VERIFIER, challenge)


def test_the_unhashed_method_compares_the_two_values_directly() -> None:
    # "plain — code_challenge = code_verifier" (section 4.2), and section 4.6:
    # "they are compared directly, i.e. code_verifier == code_challenge".
    assert PlainVerifier().verify_code_challenge(PLAIN_VERIFIER, PLAIN_VERIFIER)
    assert not PlainVerifier().verify_code_challenge(PLAIN_VERIFIER, APPENDIX_B_CHALLENGE)


def test_the_hashed_method_is_the_one_this_server_names_mandatory() -> None:
    # "S256 is Mandatory To Implement (MTI) on the server" (section 4.2).
    assert S256Verifier().get_method() == "S256"
    assert PlainVerifier().get_method() == "plain"


# Section 4.3 / 4.4 — The challenge travels with the request and is bound to
# the code


async def test_a_challenge_the_standard_would_not_accept_is_refused() -> None:
    # "code-challenge = 43*128unreserved" (section 4.3's ABNF). Each case is
    # the same refusal, so one test walks them rather than three repeating it.
    async with serving(_application()) as client:
        await _seed(client)
        owner = await _owner_token(client)
        for challenge in (TOO_SHORT, TOO_LONG, WRONG_CHARACTERS):
            answered = await _authorize(
                client,
                owner,
                code_challenge=challenge,
                code_challenge_method="S256",
            )

            assert answered.status_code == 400, challenge
            assert text_field(json_of(answered), "error") == "invalid_request"


async def test_the_code_a_client_is_handed_does_not_carry_the_challenge_in_the_clear() -> None:
    # "The server MUST NOT include the "code_challenge" value in client
    # requests in a form that other entities can extract" (section 4.4).
    async with serving(_application()) as client:
        code = await _code(
            client,
            code_challenge=APPENDIX_B_CHALLENGE,
            code_challenge_method="S256",
        )

    assert APPENDIX_B_CHALLENGE not in code


async def test_the_method_defaults_to_the_unhashed_one_when_the_request_names_none() -> None:
    # "code_challenge_method — OPTIONAL, defaults to "plain" if not present in
    # the request" (section 4.3). A client registered for the unhashed method
    # sends a challenge and no method, and the verifier that redeems the code
    # is the challenge itself.
    async with serving(_application()) as client:
        await _seed(client, plain_pkce="true")
        answered = await _authorize(
            client,
            await _owner_token(client),
            code_challenge=PLAIN_VERIFIER,
        )
        code = _delivered(answered)["code"]
        redeemed = await _redeem(client, code, code_verifier=PLAIN_VERIFIER)

    assert redeemed.status_code == 200
    assert text_field(json_of(redeemed), "access_token")


# Section 4.4.1 — Error Response


async def test_a_public_client_sending_no_challenge_is_told_the_request_is_bad() -> None:
    # "If the server requires Proof Key for Code Exchange (PKCE) by OAuth
    # public clients and the client does not send the "code_challenge" in the
    # request, the authorization endpoint MUST return the authorization error
    # response with the "error" value set to "invalid_request"" (section
    # 4.4.1).
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


async def test_a_transformation_this_server_does_not_run_is_told_the_request_is_bad() -> None:
    # "If the server supporting PKCE does not support the requested
    # transformation, the authorization endpoint MUST return the authorization
    # error response with "error" value set to "invalid_request"" (section
    # 4.4.1).
    async with serving(_application()) as client:
        await _seed(client)
        answered = await _authorize(
            client,
            await _owner_token(client),
            code_challenge=APPENDIX_B_CHALLENGE,
            code_challenge_method="S512",
        )

    assert answered.status_code == 400
    assert text_field(json_of(answered), "error") == "invalid_request"


# Section 4.5 / 4.6 — The verifier is required, and verified


async def test_a_code_tied_to_a_challenge_is_not_redeemed_without_a_verifier() -> None:
    # "code_verifier — REQUIRED" at the token endpoint when the authorization
    # request carried a challenge (section 4.5).
    async with serving(_application()) as client:
        code = await _code(
            client,
            code_challenge=APPENDIX_B_CHALLENGE,
            code_challenge_method="S256",
        )
        answered = await _redeem(client, code)

    assert answered.status_code == 400
    assert text_field(json_of(answered), "error") == "invalid_request"


async def test_the_right_verifier_redeems_the_code() -> None:
    # "If the values are equal, the token endpoint MUST continue processing as
    # normal" (section 4.6), with the standard's own vector.
    async with serving(_application()) as client:
        code = await _code(
            client,
            code_challenge=APPENDIX_B_CHALLENGE,
            code_challenge_method="S256",
        )
        answered = await _redeem(client, code, code_verifier=APPENDIX_B_VERIFIER)

    assert answered.status_code == 200
    assert text_field(json_of(answered), "access_token")


async def test_a_verifier_that_does_not_derive_the_challenge_is_an_invalid_grant() -> None:
    # "If the values are not equal, an error response indicating
    # "invalid_grant" as described in Section 5.2 of [RFC6749] MUST be
    # returned" (section 4.6).
    async with serving(_application()) as client:
        code = await _code(
            client,
            code_challenge=APPENDIX_B_CHALLENGE,
            code_challenge_method="S256",
        )
        answered = await _redeem(client, code, code_verifier=PLAIN_VERIFIER)

    assert answered.status_code == 400
    assert text_field(json_of(answered), "error") == "invalid_grant"


async def test_a_verifier_the_standard_would_not_accept_never_reaches_the_comparison() -> None:
    # "code-verifier = 43*128unreserved" (section 4.1): a value that could
    # never be a verifier is a malformed request rather than a failed proof.
    async with serving(_application()) as client:
        code = await _code(
            client,
            code_challenge=APPENDIX_B_CHALLENGE,
            code_challenge_method="S256",
        )
        answered = await _redeem(client, code, code_verifier=TOO_SHORT)

    assert answered.status_code == 400
    assert text_field(json_of(answered), "error") == "invalid_request"


# Section 7.2 — Protection against eavesdroppers


async def test_a_client_not_registered_for_the_unhashed_method_is_refused() -> None:
    # "Server implementations of this specification that support the "S256"
    # "code_challenge_method" SHOULD NOT accept "plain" unless they cannot
    # support "S256" for some technical reason" (section 7.2; RFC 9700 section
    # 2.1.1 reads the same way). The unhashed method stays available only for a
    # client whose registration says it may use it, and the client every other
    # test here registers is not one — so asking for it is refused rather than
    # quietly downgraded.
    async with serving(_application()) as client:
        await _seed(client)
        answered = await _authorize(
            client,
            await _owner_token(client),
            code_challenge=PLAIN_VERIFIER,
            code_challenge_method="plain",
        )

    assert answered.status_code == 400
    assert text_field(json_of(answered), "error") == "invalid_request"
