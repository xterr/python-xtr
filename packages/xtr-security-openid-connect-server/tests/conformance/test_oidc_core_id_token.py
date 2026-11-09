"""OpenID Connect Core 1.0 — the ID token the token endpoint answers a sign-in with.

Every token here is one the served provider issued at the end of a real code
flow. What the standard requires of its claims and its signature is read off
that token, and the token is then handed to the repository's own relying
party — its signature verifier, with strict key usage, and its claim checks —
which the provider shares no code with.
"""

from __future__ import annotations

import base64
import hashlib
from typing import TYPE_CHECKING, Final, cast
from urllib.parse import urlsplit

import anyio
import pytest
from xtr_security_core.exception import AuthenticationError
from xtr_security_http.oidc.oidc_jwks import OidcJwks

from tests.fixtures.openid_app.config import ALGORITHM, DISCOVERY_ALGORITHM, DISCOVERY_ENV
from tests.support.relying_party import relying_party_of
from tests.support.served import (
    CLIENT_ID,
    claims_of,
    header_of,
    json_of,
    openid_kernel,
    redirected_with,
    served_application,
    serving,
    text_field,
)
from tests.support.sign_in import (
    NONCE,
    authorization_query,
    authorize,
    owner_token,
    redeem,
    signed_in,
)
from tests.support.signing import ISSUER

if TYPE_CHECKING:
    from collections.abc import Mapping

    import httpx

    from tests.support.relying_party import RelyingParty

pytestmark = pytest.mark.anyio

#: What the token itself may claim: who signed in, for whom, when, and how
#: it is tied to the request and to the access token beside it.
IDENTITY_CLAIMS: Final = frozenset(
    {"iss", "sub", "aud", "exp", "iat", "auth_time", "nonce", "at_hash"},
)

#: The longest subject the standard allows.
_SUBJECT_LIMIT: Final = 255


async def _issued(env: str = "test", algorithm: str = ALGORITHM) -> tuple[str, RelyingParty]:
    """Sign in once in ``env``; return the ID token and the relying party over the provider."""
    async with serving(served_application(openid_kernel(env))) as client:
        issued = await signed_in(client)
        relying_party = await relying_party_of(client, algorithm)

    return text_field(issued, "id_token"), relying_party


async def _id_token_claims(**extra: str) -> Mapping[str, object]:
    """Sign in once with ``extra`` parameters and return what the ID token claims."""
    async with serving(served_application(openid_kernel())) as client:
        issued = await signed_in(client, **extra)

    return claims_of(text_field(issued, "id_token"))


# Section 2 — ID Token


async def test_the_issuer_is_an_https_url_with_no_query_and_no_fragment() -> None:
    # "iss ... Case-sensitive URL using the https scheme that contains scheme,
    # host, and optionally, port number and path components and no query or
    # fragment components."
    issuer = urlsplit(str((await _id_token_claims())["iss"]))

    assert issuer.scheme == "https"
    assert issuer.netloc
    assert (issuer.query, issuer.fragment) == ("", "")


async def test_the_subject_is_ascii_and_at_most_255_characters() -> None:
    # "sub ... It MUST NOT exceed 255 ASCII characters in length."
    subject = (await _id_token_claims())["sub"]

    assert isinstance(subject, str)
    assert subject.isascii()
    assert 0 < len(subject) <= _SUBJECT_LIMIT


async def test_the_audience_is_the_client_that_asked() -> None:
    # "aud ... It MUST contain the OAuth 2.0 client_id of the Relying Party as
    # an audience value."
    assert (await _id_token_claims())["aud"] == CLIENT_ID


async def test_the_token_expires_after_it_was_issued() -> None:
    # "exp ... the current time MUST be before the time represented by the
    # exp Claim"; "iat ... Time at which the JWT was issued."
    claims = await _id_token_claims()
    exp, iat = claims["exp"], claims["iat"]

    assert isinstance(exp, int)
    assert isinstance(iat, int)
    assert exp > iat


async def test_the_nonce_the_request_sent_is_claimed_unmodified() -> None:
    # "If present in the Authentication Request, Authorization Servers MUST
    # include a nonce Claim in the ID Token with the Claim Value being the
    # nonce value sent in the Authentication Request."
    assert (await _id_token_claims(nonce="a nonce/with+odd=characters"))["nonce"] == (
        "a nonce/with+odd=characters"
    )


async def test_no_nonce_is_claimed_when_the_request_sent_none() -> None:
    query = {name: value for name, value in authorization_query().items() if name != "nonce"}
    async with serving(served_application(openid_kernel())) as client:
        authorized = await client.get(
            "/authorize",
            params=query,
            headers={"Authorization": f"Bearer {await owner_token(client)}"},
        )
        issued = json_of(await redeem(client, redirected_with(authorized)["code"]))

    assert "nonce" not in claims_of(text_field(issued, "id_token"))


async def test_the_token_is_signed_with_a_real_algorithm() -> None:
    # "ID Tokens MUST be signed using JWS"; none is never used.
    id_token, _ = await _issued()

    assert header_of(id_token)["alg"] == ALGORITHM
    assert header_of(id_token)["alg"] != "none"


async def test_the_header_carries_no_key_by_value_or_by_reference() -> None:
    # "ID Tokens SHOULD NOT use the JWS or JWE x5u, x5c, jku, or jwk Header
    # Parameter fields."
    id_token, _ = await _issued()

    assert set(header_of(id_token)) <= {"typ", "alg", "kid"}


# Section 3.1.3.3 — Successful Token Response


async def test_the_token_answer_to_a_sign_in_carries_an_id_token() -> None:
    async with serving(served_application(openid_kernel())) as client:
        issued = await signed_in(client)

    assert text_field(issued, "id_token").count(".") == 2


async def test_the_token_answer_may_not_be_cached() -> None:
    # "All Token Responses that contain tokens, secrets, or other sensitive
    # information MUST include the following HTTP response header fields and
    # values: Cache-Control no-store."
    async with serving(served_application(openid_kernel())) as client:
        code = redirected_with(await authorize(client))["code"]
        answered = await redeem(client, code)

    assert answered.status_code == 200
    assert answered.headers["cache-control"] == "no-store"
    assert answered.headers["pragma"] == "no-cache"


# Section 3.1.3.6 — ID Token, the access token hash


async def test_the_at_hash_is_the_left_half_of_the_access_tokens_hash() -> None:
    # "Its value is the base64url encoding of the left-most half of the hash
    # of the octets of the ASCII representation of the access_token value,
    # where the hash algorithm used is the hash algorithm used in the alg
    # Header Parameter of the ID Token's JOSE Header." ES256 hashes with SHA-256.
    async with serving(served_application(openid_kernel())) as client:
        issued = await signed_in(client)

    digest = hashlib.sha256(text_field(issued, "access_token").encode("ascii")).digest()
    expected = base64.urlsafe_b64encode(digest[:16]).rstrip(b"=").decode("ascii")
    assert claims_of(text_field(issued, "id_token"))["at_hash"] == expected


# Section 3.1.3.7 — ID Token Validation, by the relying party


async def test_the_relying_party_accepts_the_id_token() -> None:
    # The signature against the published key set, then the issuer, the
    # audience, the time claims and the nonce.
    id_token, relying_party = await _issued()

    claims = await relying_party.signature_verifier.verify(id_token)
    relying_party.id_token.validate_claims(claims, ISSUER, CLIENT_ID, NONCE)

    assert claims["sub"]


async def test_an_id_token_changed_by_one_character_is_refused() -> None:
    id_token, relying_party = await _issued()
    header, payload, signature = id_token.split(".")
    middle = len(signature) // 2
    swapped = "B" if signature[middle] == "A" else "A"
    tampered = f"{header}.{payload}.{signature[:middle]}{swapped}{signature[middle + 1 :]}"

    with pytest.raises(AuthenticationError):
        _ = await relying_party.signature_verifier.verify(tampered)


# Section 5.4 — the scope claims are the userinfo endpoint's


async def test_the_id_token_claims_who_signed_in_and_nothing_a_scope_reveals() -> None:
    claims = await _id_token_claims(scope="openid read")

    assert set(claims) <= IDENTITY_CLAIMS


# Section 10.1 — Signing


async def test_the_token_names_the_published_key_it_was_signed_with() -> None:
    # "If there are multiple keys in the referenced JWK Set document, a kid
    # value MUST be provided in the JOSE Header."
    async with serving(served_application(openid_kernel())) as client:
        id_token = text_field(await signed_in(client), "id_token")
        published = json_of(await client.get("/.well-known/jwks.json"))

    keys = cast("list[Mapping[str, object]]", published["keys"])
    assert header_of(id_token)["kid"] in {key["kid"] for key in keys}


async def test_a_verifier_checking_key_usage_strictly_keeps_every_published_key() -> None:
    async with serving(served_application(openid_kernel())) as client:
        published = json_of(await client.get("/.well-known/jwks.json"))
        relying_party = await relying_party_of(client, ALGORITHM)

    answered = await relying_party.http_client.request("GET", f"{ISSUER}/.well-known/jwks.json")
    kept, _ = await OidcJwks.from_response(answered, enforce_key_usage_verification=True)

    assert kept
    assert kept == published["keys"]


# Section 15.1 — Mandatory to Implement Features for All OpenID Providers


async def test_a_token_signed_with_rs256_is_accepted_by_the_relying_party() -> None:
    # "OPs MUST support signing ID Tokens with the RSA SHA-256 algorithm."
    id_token, relying_party = await _issued(DISCOVERY_ENV, DISCOVERY_ALGORITHM)

    claims = await relying_party.signature_verifier.verify(id_token)
    relying_party.id_token.validate_claims(claims, ISSUER, CLIENT_ID, NONCE)

    assert header_of(id_token)["alg"] == "RS256"


# The issuer is the deployment's, never the request's


async def test_the_issuer_does_not_follow_the_host_the_request_names() -> None:
    hostile = {"host": "evil.example"}
    async with serving(served_application(openid_kernel())) as client:
        code = redirected_with(await authorize(client))["code"]
        answered = await redeem(client, code, headers=hostile)

    assert answered.status_code == 200, answered.text
    assert claims_of(text_field(json_of(answered), "id_token"))["iss"] == ISSUER


# Each answer states its own sign-in


async def test_two_codes_redeemed_at_once_each_carry_their_own_nonce() -> None:
    async with serving(served_application(openid_kernel())) as client:
        codes = {
            nonce: redirected_with(await authorize(client, nonce=nonce))["code"]
            for nonce in ("a", "b")
        }
        answers: dict[str, httpx.Response] = {}

        async def redeemed(nonce: str) -> None:
            answers[nonce] = await redeem(client, codes[nonce])

        async with anyio.create_task_group() as group:
            for nonce in codes:
                _ = group.start_soon(redeemed, nonce)

    claimed = {
        nonce: claims_of(text_field(json_of(answer), "id_token"))["nonce"]
        for nonce, answer in answers.items()
    }
    assert claimed == {"a": "a", "b": "b"}
